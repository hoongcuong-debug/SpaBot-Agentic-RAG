import asyncio
import uuid
from typing import Any

from langchain_core.messages import AIMessage

from core.graph.build_graph import create_main_graph
from core.graph.state import init_state


async def stream_graph_events(graph: Any, state: dict, config: dict):
    """
    Hàm này nhận graph, state, và config, sau đó thực hiện stream các sự kiện
    và in ra nội dung tin nhắn từ AI một cách tường minh.
    """
    last_printed_content = None
    try:
        # Bắt đầu stream các sự kiện từ graph
        async for event in graph.astream(state, config=config):
            # Lặp qua các node trong sự kiện
            for key, value in event.items():
                # Chỉ xử lý các sự kiện từ các node agent, bỏ qua supervisor
                if key != "supervisor" and "__end__" not in key:
                    messages = value.get("messages", [])
                    if messages:
                        # Lấy tin nhắn cuối cùng trong danh sách
                        last_message = messages[-1]
                        # Kiểm tra nếu là tin nhắn từ AI và có nội dung mới
                        if isinstance(last_message, AIMessage):
                            content = last_message.content.strip()
                            if content and content != last_printed_content:
                                print(f"\n🤖 Bot says: {content}\n")
                                last_printed_content = content
    except Exception as e:
        print(f"\n--- Đã có lỗi xảy ra trong quá trình stream: {e} ---")


async def main():
    """
    Hàm chính để khởi tạo và chạy vòng lặp chat tương tác trên terminal.
    """
    # 1. Khởi tạo graph chính của ứng dụng
    graph = create_main_graph()
    print("✅ Graph đã được khởi tạo thành công!")

    # 2. Thiết lập state và config ban đầu cho phiên chat
    state = init_state()
    session_id = str(uuid.uuid4())  # Tạo một ID phiên duy nhất
    config = {"configurable": {"thread_id": session_id}}
    print(f"Bắt đầu phiên chat mới với ID: {session_id}")
    print("-------------------------------------------------")
    print("Nhập 'exit' hoặc nhấn Ctrl+C để kết thúc.")
    print("-------------------------------------------------")

    # 3. Bắt đầu vòng lặp chat
    while True:
        try:
            # Lấy input từ người dùng
            user_input = input("😎 You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 Hẹn gặp lại!")
                break
            
            # Cập nhật state với thông tin mới
            state["user_input"] = user_input
            # Trong môi trường test, ta có thể giả lập chat_id
            state["chat_id"] = "1377999563" 

            # Gọi hàm để xử lý và stream phản hồi
            await stream_graph_events(graph, state, config)

        except (KeyboardInterrupt, EOFError):
            print("\n👋 Hẹn gặp lại!")
            break
        except Exception as e:
            print(f"\n--- Lỗi không mong muốn: {e} ---")
            print("--- Vui lòng thử lại. ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nChương trình đã được tắt.")