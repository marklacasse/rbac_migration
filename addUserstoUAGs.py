import requests
import json
from config_loader import load_config, get_headers

# Load configuration from .env file
config = load_config()
API_KEY = config['API_KEY']
BASE_URL = config['BASE_URL']
AUTH = config['AUTH']
ORG = config['ORG']

headers = get_headers(config)

GET_GROUPS_EXPANDED_ENDPOINT = "{}/Contrast/api/ng/{}/groups?expand=users,skip_links".format(BASE_URL, ORG)
GET_GROUP_DETAILS_ENDPOINT = "{}/Contrast/api/ng/{}/groups/{}".format(BASE_URL, ORG, "{}")
GET_UAG_ENDPOINT = "{}/api/v4/organizations/{}/user-access-groups".format(BASE_URL, ORG) # Removed trailing slash for correct ID append


def get_groups_expanded():
    """
    Fetches all groups with expanded user and application information.
    """
    url = GET_GROUPS_EXPANDED_ENDPOINT
    print(f"GETting groups: {url}") # Print URL
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch groups with expanded information: {e}")
        return None

def get_group_details(group_id):
    """
    Fetches details for a specific group.
    """
    url = GET_GROUP_DETAILS_ENDPOINT.format(group_id)
    print(f"GETting group details: {url}") # Print URL
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch details for group ID {group_id}: {e}")
        return None
    
def get_uag_uuid(group_name):
    """
    Retrieves ID and role IDs for a specific UAG.
    Returns (uag_id, list_of_role_ids) or (None, None) on failure/not found.
    """
    query_url = f"{GET_UAG_ENDPOINT}?nameFilter={group_name}"
    print(f"GETting UAG info: {query_url}") # Print URL
    try:
        response = requests.get(query_url, headers=headers) # Changed rgresponse to response
        response.raise_for_status() # Use raise_for_status for consistency
        res = response.json()

        if 'content' in res and len(res['content']) > 0:
            uag_data = res['content'][0]
            retrieved_uag_id = uag_data.get('id')
            retrieved_role_ids = uag_data.get('roleIds', [])
            print(f"Found UAG '{group_name}'. ID: {retrieved_uag_id}, Role IDs: {retrieved_role_ids}")
            return retrieved_uag_id, retrieved_role_ids
        else:
            print(f"WARNING: UAG with name '{group_name}' not found or content is empty in response.")
            return None, None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch UAG info for '{group_name}': {e}")
        return None, None


def update_uag(user_ids_to_add, group_name):
    """
    Update a UAG by its name, setting new user IDs and keeping existing role IDs.
    """
    uag_id, current_role_ids = get_uag_uuid(group_name)

    if uag_id is None:
        print(f"WARNING: Cannot update UAG '{group_name}'. UAG not found or an error occurred during lookup.")
        return None # Return None to indicate update failed

    update_payload = {
        "name": group_name,
        "description": f"Edit user access group for {group_name}",
        "roleIds": current_role_ids, # Using the role IDs retrieved from get_uag_uuid
        "userIds": user_ids_to_add
    }

    # API for updating UAG is typically PUT to its specific ID endpoint
    update_url = f"{GET_UAG_ENDPOINT}/{uag_id}" # Correctly append UAG ID
    print(f"PUTting UAG update: {update_url}") # Print URL
    print(f"Payload for '{group_name}': {json.dumps(update_payload)}") # Print payload

    response = None
    try:
        response = requests.put(update_url, headers=headers, data=json.dumps(update_payload))
        response.raise_for_status()
        print(f"SUCCESS: UAG '{group_name}' updated successfully!")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to update UAG '{group_name}' (ID: {uag_id}): {e}")
        if response is not None:
            print(f"Response status code: {response.status_code}")
            print(f"Response text: {response.text}")
        return None
    

def main():
    """
    Fetches groups, iterates through non-readonly groups,
    retrieves user IDs from group details, and updates corresponding UAGs.
    """
    print("Starting UAG synchronization script...")
    print("This script adds users to UAGs created by rbac_migration.py")
    print("=" * 50)

    groups_data = get_groups_expanded()
    
    if not groups_data:
        print("ERROR: Failed to fetch groups data.")
        return

    # Extract groups using the same logic as rbac_migration.py
    all_groups = []
    
    # Add custom groups
    custom_groups = groups_data.get('custom_groups', {})
    if isinstance(custom_groups, dict):
        for group_list in custom_groups.values():
            if isinstance(group_list, list):
                all_groups.extend(group_list)
    
    # Add predefined groups  
    predefined_groups = groups_data.get('predefined_groups', {})
    if isinstance(predefined_groups, dict):
        for group_list in predefined_groups.values():
            if isinstance(group_list, list):
                all_groups.extend(group_list)

    if not all_groups:
        print("ERROR: No groups found in API response.")
        return
        
    print(f"Found {len(all_groups)} groups to process")
    
    processed_count = 0
    success_count = 0

    for group in all_groups:
        group_id = group.get('group_id')
        group_name = group.get('name')
        readonly = group.get('readonly')

        if not group_id or not group_name:
            print(f"WARNING: Skipping malformed group entry (missing ID or Name): {group}")
            continue
            
        processed_count += 1
        
        if readonly:
            print(f"--- Skipping Readonly Group: '{group_name}' (ID: {group_id}) ---")
            continue
            
        print(f"\n--- Processing Group {processed_count}: '{group_name}' (ID: {group_id}) ---")
        
        group_details = get_group_details(group_id)

        if not group_details or 'group' not in group_details:
            print(f"  WARNING: Failed to retrieve detailed information for group ID: {group_id}. Skipping.")
            continue
            
        user_ids_in_group = []
        if 'users' in group_details['group'] and isinstance(group_details['group']['users'], list):
            for user in group_details['group']['users']:
                user_id = user.get('id')
                if user_id:
                    user_ids_in_group.append(user_id)
        else:
            print(f"  WARNING: No 'users' data found for group '{group_name}' in group details.")

        if not user_ids_in_group:
            print(f"  WARNING: No user IDs found in group '{group_name}'. Skipping UAG update.")
            continue
            
        print(f"  Found {len(user_ids_in_group)} user IDs in group '{group_name}'.")
        # Print first few user IDs for console feedback
        user_preview = user_ids_in_group[:3] if len(user_ids_in_group) <= 3 else user_ids_in_group[:3] + ['...']
        print(f"  Users in '{group_name}': {user_preview} ({len(user_ids_in_group)} total)")

        # UAGs created by rbac_migration.py use exact group name matching
        uag_name = group_name

        update_response = update_uag(user_ids_in_group, uag_name)
        if update_response:
            print(f"  ✓ SUCCESS: UAG '{uag_name}' updated successfully!")
            success_count += 1
        else:
            print(f"  ✗ FAILED: UAG '{uag_name}' update failed.")

    print("\n" + "=" * 50)
    print("UAG USER MIGRATION SUMMARY")
    print("=" * 50)
    print(f"Groups processed: {processed_count}")
    print(f"UAGs updated successfully: {success_count}")
    print(f"Failed updates: {processed_count - success_count}")
    print("Script finished.")

if __name__ == "__main__":
    main()
