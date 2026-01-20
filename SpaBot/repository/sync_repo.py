import json
from supabase import Client
from datetime import date, time, timedelta, datetime

class CustomerRepo:
    def __init__(self, supabase_client: Client):
        self.supabase_client = supabase_client
        
    def create_customer(self, chat_id: str) -> dict | None:
        response = (
            self.supabase_client.table("customer")
            .insert({"chat_id": chat_id})
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def get_customer_by_chat_id(
        self, 
        chat_id: str
    ) -> dict | None:
        response = (
            self.supabase_client.table("customer")
            .select("*")
            .eq("chat_id", chat_id)
            .execute()
        )

        return response.data[0] if response.data else None
    
    def get_or_create_customer(self, chat_id: str) -> dict | None:
        response = (
            self.supabase_client.table("customers")
            .upsert(
                {"chat_id": chat_id},
                on_conflict="chat_id"
            )
            .execute()
        )

        return response.data[0] if response.data else None
    
    def check_customer_id(self, customer_id: int) -> bool:
        response = (
            self.supabase_client.table('customers')
            .select('id')
            .eq("id", customer_id)
            .execute()
        )
        
        return True if response.data else False
    
    def update_customer_by_customer_id(
        self, 
        update_payload: dict, 
        customer_id: int
    ) -> dict | None:
        response = (
            self.supabase_client.table('customers')
            .update(update_payload)
            .eq('id', customer_id)
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def update_customer_by_chat_id(
        self, 
        update_payload: dict, 
        chat_id: str
    ) -> dict | None:
        response = (
            self.supabase_client.table('customers')
            .update(update_payload)
            .eq('chat_id', chat_id)
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def get_uuid(self, chat_id: str) -> str | None:
        res = (
            self.supabase_client.table("customers")
                .select("uuid")
                .eq("chat_id", chat_id)
                .execute()
        )

        return res.data[0]["uuid"] if res.data else None
    
    def delete_customer(self, chat_id: str) -> bool:
        response = (
            self.supabase_client.table('customers')
            .delete()
            .eq('chat_id', chat_id)
            .execute()
        )
        
        return bool(response.data)
    
    def add_complaints(self, complaint_payload: dict) -> dict | None:
        response = (
            self.supabase_client.table('complaints')
            .insert(complaint_payload)
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def is_new_customer(self, customer_id: int) -> bool:
        response = (
            self.supabase_client.table('appointments')
            .select('id')
            .eq('customer_id', customer_id)
            .execute()
        )
        
        return False if response.data else True
    
    
class ServiceRepo:
    def __init__(self, supabase_client: Client):
        self.supabase_client = supabase_client
        
    def get_service_by_keyword(self, keyword: str) -> list[dict] | None:
        pattern = f"%{keyword}%"

        response = (
            self.supabase_client
            .from_("services")
            .select("*, service_discounts(discount_value)")
            .or_(f"name.ilike.{pattern},description.ilike.{pattern},type.ilike.{pattern}")
            .execute()
        )
        
        return response.data if response.data else None
    
    def get_services_by_ids(
        self, 
        service_id_list: list[int]
    ) -> list[dict] | None:
        response = (
            self.supabase_client
            .table("services")
            .select("*, service_discounts(discount_value)")
            .in_("id", service_id_list)
            .execute()
        )
        
        return response.data if response.data else None
    
    def get_qna_by_ids(
        self, 
        qna_id_list: list[int]
    ) -> list[dict] | None:
        response = (
            self.supabase_client
            .table("qna")
            .select("*")
            .in_("id", qna_id_list)
            .execute()
        )
        
        return response.data if response.data else None
    
    def get_services_by_embedding(
        self, 
        query_embedding: list[float],
        match_count: int = 5
    ) -> list[dict] | None:
        response = self.supabase_client.rpc(
            "match_services_embedding",
            {
                "query_embedding": query_embedding, 
                "match_count": match_count
            }
        ).execute()
        
        if not response.data:
            return None

        results = [
            {
                "id": data["id"],
                "service_id": data["service_id"],
                "similarity": data["similarity"],
            }
            for data in response.data
        ]
        
        return results    
    
    def get_qna_by_embedding(
        self, 
        query_embedding: list[float], 
        match_count: int = 3
    ) -> list[dict] | None:
        response = self.supabase_client.rpc(
            "match_qna_embedding",
            {
                "query_embedding": query_embedding,
                "match_count": match_count,
            }
        ).execute()
        
        if not response.data:
            return None

        results = [
            {
                "id": data["id"],
                "qna_id": data["qna_id"],
                "similarity": data["similarity"],
            }
            for data in response.data
        ]
        
        return results
    
    def get_all_services_without_des(self) -> list[dict]:
        response = (
            self.supabase_client
            .table("services")
            .select("id, type, name, duration_minutes, price")
            .order("type")
            .execute()
        )
        
        return response.data if response.data else None
    
    
class RoomRepo:
    def __init__(self, supabase_client: Client):
        self.supabase_client = supabase_client
        
    def get_all_rooms(self) -> list[dict] | None:
        response = (
            self.supabase_client.table('rooms')
            .select("id", "capacity")
            .execute()
        )
        
        return response.data if response.data else None
    
    def get_all_rooms_return_dict(self) -> dict | None:
        response = (
            self.supabase_client.table('rooms')
            .select("id", "name", "capacity")
            .execute()
        )
        
        if not response.data:
            return None
        
        rooms_dict = {}
        for data in response.data:
            rooms_dict[data["id"]] = {
                "name": data["name"],
                "capacity": data["capacity"]
            }
        
        return rooms_dict
    
    
class AppointmentRepo:
    def __init__(self, supabase_client: Client):
        self.supabase_client = supabase_client
        
    def get_appointment_by_booking_date(
        self, 
        booking_date: str
    ) -> list[dict] | None:
        response = (
            self.supabase_client
            .table("appointments")
            .select("id, staff_id, room_id, start_time, end_time")
            .eq("booking_date", booking_date)
            .eq("status", "booked")
            .order("start_time", desc=False)
            .execute()
        )
        
        return response.data if response.data else None
        
    def get_overlap_appointments(
        self, 
        booking_date_new: date, 
        start_time_new: time,
        end_time_new: time,
        buffer_time: int = 5
    ) -> list[dict]:
        buffer = timedelta(minutes=buffer_time)
        
         # Tạo datetime giả để cộng buffer
        dt_start = datetime.combine(booking_date_new, start_time_new)
        dt_end = datetime.combine(booking_date_new, end_time_new)

        # cộng buffer
        dt_start_buffered = dt_start - buffer
        dt_end_buffered = dt_end + buffer

        # lấy lại phần time sau khi buffer
        start_time_threshold = dt_start_buffered.time()
        end_time_threshold = dt_end_buffered.time()
        
        response = (
            self.supabase_client
            .table("appointments")
            .select("*")
            .eq("booking_date", booking_date_new)
            .in_("status", ["booked", "completed"])
            .lt("start_time", end_time_threshold)
            .gt("end_time", start_time_threshold)
            .execute()
        )
        
        return response.data if response.data else None
    
    def create_appointment(self, appointment_payload: dict) -> dict | None:
        response = (
            self.supabase_client.table('appointments')
            .insert(appointment_payload)
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def create_appointment_services_item_bulk(self, services_to_insert: list[dict]) -> dict | None:
        response = (
            self.supabase_client.table('appointment_services')
            .insert(services_to_insert)
            .execute()
        )
        
        return response.data[0] if response.data else None
    
    def get_appointment_details(self, appointment_id: int) -> dict | None:
        response = (
            self.supabase_client
            .table("appointments")
            .select("""
                *,
                appointment_services (
                    services (
                        id,
                        type,
                        name,
                        duration_minutes,
                        price,
                        service_discounts (discount_value)
                    )
                ),
                customer:customers!fk_appointments_customer (
                    id,
                    name,
                    phone,
                    email
                ),
                staff:staffs!fk_appointments_staff (
                    id,
                    name
                ),
                room:rooms!fk_appointments_room (
                    id,
                    name
                )
            """)
            .eq("id", appointment_id)
            .single()
            .execute()
        )

        return response.data if response.data else None
    
    def update_appointment(
        self, 
        appointment_id: int, 
        update_payload: dict
    ) -> bool:
        response = (
            self.supabase_client
            .table("appointments")
            .update(update_payload)
            .eq("id", appointment_id)
            .execute()
        )
        
        return bool(response.data)
    
    def get_all_booked_appointments(self, customer_id: int) -> list[dict] | None:
        """
        Lấy tất cả các lịch hẹn có trạng thái là 'booked' theo customer_id.

        Args:
            - customer_id (int): ID của khách hàng.

        Returns:
            - list[dict] | None: Danh sách các lịch hẹn hoặc None nếu không có lịch nào.
        """
        response = (
            self.supabase_client
            .table("appointments")
            .select("""
                *,
                appointment_services (
                    services (
                        id,
                        type,
                        name,
                        duration_minutes,
                        price
                    )
                ),
                customer:customers!fk_appointments_customer (
                    id,
                    name,
                    phone,
                    email
                ),
                staff:staffs!fk_appointments_staff (
                    id,
                    name
                ),
                room:rooms!fk_appointments_room (
                    id,
                    name
                )
            """)
            .eq("status", "booked")
            .eq("customer_id", customer_id)
            .order("booking_date", desc=False)
            .execute()
        )
        
        return response.data if response.data else None
    
    def get_all_appointments(self, customer_id: int) -> list[dict] | None:
        """
        Lấy tất cả các lịch hẹn có mọi trạng thái theo customer_id.

        Args:
            - customer_id (int): ID của khách hàng.

        Returns:
            - list[dict] | None: Danh sách các lịch hẹn hoặc None nếu không có lịch nào.
        """
        response = (
            self.supabase_client
            .table("appointments")
            .select("""
                *,
                appointment_services (
                    services (
                        id,
                        type,
                        name,
                        duration_minutes,
                        price
                    )
                ),
                customer:customers!fk_appointments_customer (
                    id,
                    name,
                    phone,
                    email
                ),
                staff:staffs!fk_appointments_staff (
                    id,
                    name
                ),
                room:rooms!fk_appointments_room (
                    id,
                    name
                )
            """)
            .eq("customer_id", customer_id)
            .order("booking_date", desc=False)
            .execute()
        )
        
        return response.data if response.data else None
    

class StaffRepo:
    def __init__(self, supabase_client: Client):
        self.supabase_client = supabase_client
        
    def get_all_staff_return_dict(self) -> dict | None:
        response = (
            self.supabase_client.table('staffs')
            .select("id", "name")
            .execute()
        )
        
        if not response.data:
            return None
        
        staff_dict = {}
        for data in response.data:
            staff_dict[data["id"]] = data["name"]
        
        return staff_dict
