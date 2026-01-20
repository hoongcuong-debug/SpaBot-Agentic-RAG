import time
import asyncio
import threading
from typing import Dict

from core.utils.function import update_state_customer
from log.logger_config import setup_logging

logger = setup_logging(__name__)

class StateCleanupManager:
    def __init__(self, graph, cleanup_interval_minutes=30, state_ttl_minutes=60):
        """
        Args:
            graph: LangGraph instance
            cleanup_interval_minutes: Khoảng thời gian chạy cleanup task (phút)
            state_ttl_minutes: Thời gian sống của state (phút)
        """
        self.graph = graph
        self.cleanup_interval = cleanup_interval_minutes * 60  # Convert to seconds
        self.state_ttl = state_ttl_minutes * 60  # Convert to seconds
        self.thread_timestamps: Dict[str, float] = {}
        self.cleanup_task = None
        self.is_running = False
        
    def register_thread(self, thread_id: str):
        """Đăng ký thread_id mới với timestamp hiện tại"""
        self.thread_timestamps[thread_id] = time.time()
        logger.info(f"Registered thread {thread_id} for cleanup")
    
    def update_thread_access(self, thread_id: str):
        """Cập nhật thời gian truy cập cuối của thread"""
        self.thread_timestamps[thread_id] = time.time()
    
    def start_cleanup_task(self):
        """Bắt đầu background cleanup task"""
        if self.is_running:
            logger.warning("Cleanup task is already running")
            return
            
        self.is_running = True
        
        # Sử dụng asyncio.create_task cho async environment
        if asyncio.get_event_loop().is_running():
            self.cleanup_task = asyncio.create_task(self._async_cleanup_loop())
        else:
            # Sử dụng threading cho sync environment
            self.cleanup_task = threading.Thread(target=self._sync_cleanup_loop, daemon=True)
            self.cleanup_task.start()
            
        logger.info("Started state cleanup background task")
    
    def stop_cleanup_task(self):
        """Dừng background cleanup task"""
        self.is_running = False
        if self.cleanup_task:
            if hasattr(self.cleanup_task, 'cancel'):
                self.cleanup_task.cancel()
        logger.info("Stopped state cleanup background task")
    
    async def _async_cleanup_loop(self):
        """Async cleanup loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_states()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in async cleanup loop: {e}")
    
    def _sync_cleanup_loop(self):
        """Sync cleanup loop"""
        while self.is_running:
            try:
                time.sleep(self.cleanup_interval)
                asyncio.run(self._cleanup_expired_states())
            except Exception as e:
                logger.error(f"Error in sync cleanup loop: {e}")
    
    async def _cleanup_expired_states(self):
        """Xóa các state đã hết hạn"""
        current_time = time.time()
        expired_threads = []
        
        for thread_id, timestamp in list(self.thread_timestamps.items()):
            if current_time - timestamp > self.state_ttl:
                expired_threads.append(thread_id)
        
        if expired_threads:
            logger.info(f"Cleaning up {len(expired_threads)} expired threads")
            
            # Xóa state từ database/memory
            for thread_id in expired_threads:
                try:
                    # Cập nhật state bị xoá vào DB
                    await update_state_customer(
                        chat_id=thread_id,
                        graph=self.graph
                    )
                    
                    logger.info("Update state in customer successful")
                    
                    # Xóa state từ LangGraph checkpointer
                    self.graph.checkpointer.delete_thread(thread_id)
                    
                    # Xóa khỏi tracking dictionary
                    del self.thread_timestamps[thread_id]
                    
                    logger.info(f"Deleted state for thread {thread_id}")
                except Exception as e:
                    logger.error(f"Failed to delete state for thread {thread_id}: {e}")