from googleapiclient.discovery import build

def get_google_user_info(credentials):
    """
    Get user info from Google credentials (e.g., name, email).
    """
    try:
        # Use Google API to fetch user info from the credentials
        # This is just an example of how you might get user info using Google API
        service = build("people", "v1", credentials=credentials)
        profile = service.people().get(resourceName="people/me", personFields="names,emailAddresses").execute()
        
        user_info = {
            "name": profile["names"][0]["displayName"],
            "email": profile["emailAddresses"][0]["value"]
        }
        
        return user_info
    except Exception as e:
        raise Exception(f"Error fetching Google user info: {str(e)}")
