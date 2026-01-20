import os
import time
from supabase import create_client, Client
from supabase import SupabaseException
from connection import get_supabase_client

supabase_client = get_supabase_client()

def check_supabase_connection(supabase: Client, test_table: str = None, timeout_ms: float = 5000.0) -> bool:
    try:
        start = time.time()
        if test_table:
            res = supabase.table(test_table).select("id", "capacity").execute()
        else:
            res = supabase.table("products").select("*").limit(1).execute()
            
        print(res)
        latency = (time.time() - start) * 1000
        if latency > timeout_ms:
            print(f"Connection test failed: error={res.error}, latency={latency:.1f} ms")
            return False
        return True
    except SupabaseException as e:
        print(f"Supabase connection error: {e}")
        return False
    
check_supabase_connection(supabase=supabase_client, test_table="rooms")