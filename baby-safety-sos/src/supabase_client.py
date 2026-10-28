from supabase import create_client

# Replace these with your Supabase project URL and publishable key.
SUPABASE_URL = "https://xxgodnlpskeosihykltn.supabase.co"
SUPABASE_PUBLIC_KEY = "sb_publishable_bJr-RU_UXVB1RApA0Qvubw_Yw7-5H6K"


def create_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_PUBLIC_KEY)


supabase = create_supabase_client()
