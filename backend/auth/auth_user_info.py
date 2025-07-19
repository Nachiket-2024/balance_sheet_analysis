from googleapiclient.discovery import build

def get_google_user_info(credentials):
    """
    Fetch user info from Google credentials (e.g., name, email).
    
    Args:
        credentials: OAuth2 credentials obtained after authentication
        
    Returns:
        A dictionary containing user's name and email
        
    Raises:
        Exception: If there is an error while fetching user info from Google
    """
    try:
        # Use Google People API to fetch user info from the credentials
        service = build("people", "v1", credentials=credentials)
        
        # Fetch profile information (name and email)
        profile = service.people().get(resourceName="people/me", personFields="names,emailAddresses").execute()

        # Extracting name and email from the profile
        user_info = {
            "name": profile["names"][0]["displayName"],
            "email": profile["emailAddresses"][0]["value"]
        }
        
        return user_info

    except Exception as e:
        # Log and raise the error if fetching user info fails
        raise Exception(f"Error fetching Google user info: {str(e)}")
