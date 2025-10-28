import requests
import json
import os
from config_loader import load_config, get_headers
from datetime import datetime
import logging

# Load configuration first
config = load_config()

# Setup logging - use configurable LOG_DIR
logs_dir = config['LOG_DIR']
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

today_date = datetime.now()
date_time = today_date.strftime('%Y-%m-%d')
log_file_name = f'{logs_dir}/rbac_migration_logs_{date_time}.txt'

logging.basicConfig(filename=log_file_name, level=logging.INFO,
                   format='%(asctime)s %(levelname)s %(message)s', 
                   datefmt='%Y-%m-%d %H:%M:%S')
API_KEY = config['API_KEY']
BASE_URL = config['BASE_URL']
AUTH = config['AUTH']
ORG = config['ORG']

headers = get_headers(config)

# API Endpoints
GET_GROUPS_EXPANDED_ENDPOINT = f"{BASE_URL}/Contrast/api/ng/{ORG}/groups?expand=users,applications,skip_links"
GET_RESOURCE_GROUPS_ENDPOINT = f"{BASE_URL}/api/v4/organizations/{ORG}/resource-groups"
GET_ROLES_ENDPOINT = f"{BASE_URL}/api/v4/organizations/{ORG}/roles"
GET_USER_ACCESS_GROUPS_ENDPOINT = f"{BASE_URL}/api/v4/organizations/{ORG}/user-access-groups"
GET_USERS_ENDPOINT = f"{BASE_URL}/Contrast/api/ng/{ORG}/users"

# Role mapping configuration - customize based on your organization's needs
ROLE_MAPPING = {
    # Organization roles to RBAC role permissions
    'view': {
        'actions': ['APPLICATION_VIEW', 'VIEW_ATTACK_DATA'],
        'is_org_viewer': True
    },
    'edit': {
        'actions': ['EDIT', 'APPLICATION_EDIT', 'APPLICATION_VIEW', 'PROTECT_ACCESS', 
                   'APPLICATION_RULES_ADMIN', 'PROTECT_EXCLUSIONS_MANAGE', 
                   'PROTECT_POLICIES_MANAGE', 'VIEW_ATTACK_DATA'],
        'is_org_viewer': False
    },
    'rules_admin': {
        'actions': ['EDIT', 'APPLICATION_EDIT', 'APPLICATION_VIEW', 'PROTECT_ACCESS',
                   'APPLICATION_RULES_ADMIN', 'PROTECT_EXCLUSIONS_MANAGE',
                   'PROTECT_POLICIES_MANAGE', 'PROTECT_SENSITIVE_DATA_POLICY_MANAGE',
                   'VIEW_ATTACK_DATA'],
        'is_org_viewer': False
    },
    'admin': {
        'actions': ['EDIT', 'RESOURCE_GROUP_PROJECT_CREATE', 'APPLICATION_EDIT', 
                   'APPLICATION_VIEW', 'PROTECT_ACCESS', 'APPLICATION_RULES_ADMIN',
                   'PROTECT_EXCLUSIONS_MANAGE', 'PROTECT_POLICIES_MANAGE',
                   'PROTECT_SENSITIVE_DATA_POLICY_MANAGE', 'SAST_SCAN_UPLOAD',
                   'VIEW_ATTACK_DATA', 'SAST_PROJECT_EDIT', 'SAST_PROJECT_VIEW'],
        'is_org_viewer': False
    }
}

def get_all_groups():
    """Fetch all groups with expanded user and application information."""
    print(f"Fetching all groups from: {GET_GROUPS_EXPANDED_ENDPOINT}")
    try:
        response = requests.get(GET_GROUPS_EXPANDED_ENDPOINT, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch groups: {e}")
        return None

def find_resource_group_by_name(name):
    """Check if a resource group already exists."""
    try:
        url = f"{GET_RESOURCE_GROUPS_ENDPOINT}?nameFilter={name}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['content'][0] if data['content'] else None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking resource group {name}: {e}")
        return None

def create_resource_group(name, app_ids):
    """Create a resource group with associated applications."""
    if not app_ids:
        logging.warning(f"No application IDs for group {name}. Skipping resource group creation.")
        return None
        
    payload = {
        'name': name,
        'description': f'Resource Group for {name}',
        'resourceGroupIds': [],
        'resourceIdMap': {
            'APPLICATION': app_ids
        }
    }
    
    try:
        response = requests.post(GET_RESOURCE_GROUPS_ENDPOINT, 
                               headers=headers, 
                               data=json.dumps(payload))
        if response.status_code == 201:
            rg = response.json()
            logging.info(f"Resource Group '{name}' created successfully with ID: {rg['id']}")
            return rg
        elif response.status_code == 409:
            logging.warning(f"Resource Group '{name}' already exists")
            return find_resource_group_by_name(name)
        else:
            logging.error(f"Failed to create Resource Group '{name}': {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating resource group {name}: {e}")
        return None

def create_role(name, description, actions, resource_group_ids):
    """Create a role with specified permissions."""
    payload = {
        'name': name,
        'description': description,
        'actions': actions,
        'resourceGroupIds': resource_group_ids
    }
    
    try:
        response = requests.post(GET_ROLES_ENDPOINT, 
                               headers=headers, 
                               data=json.dumps(payload))
        if response.status_code == 201:
            role = response.json()
            logging.info(f"Role '{name}' created successfully with ID: {role['id']}")
            return role
        elif response.status_code == 409:
            logging.warning(f"Role '{name}' already exists")
            return None  # Could fetch existing role if needed
        else:
            logging.error(f"Failed to create Role '{name}': {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating role {name}: {e}")
        return None

def get_organization_view_role_id():
    """Find and return the ID of the built-in Organization Viewer role."""
    try:
        # Search for roles - get more results to ensure we find the right one
        response = requests.get(f"{GET_ROLES_ENDPOINT}?size=500", headers=headers)
        if response.status_code == 200:
            data = response.json()
            roles = data.get('content', [])
            
            print(f"    Searching through {len(roles)} roles for Organization Viewer...")
            
            # First, look for exact matches of Organization Viewer role
            exact_matches = [
                'Organization Viewer',
                'Organization View',
                'Org Viewer',
                'Organization Reader'
            ]
            
            for role in roles:
                role_name = role.get('name', '')
                for exact_name in exact_matches:
                    if role_name.lower() == exact_name.lower():
                        print(f"    Found exact Organization Viewer role: {role_name} (ID: {role['id']})")
                        logging.info(f"Found Organization Viewer role: {role_name} (ID: {role['id']})")
                        return role['id']
            
            # Second, look for roles containing "Organization" and "View" but exclude SCA-specific ones
            for role in roles:
                role_name = role.get('name', '')
                role_lower = role_name.lower()
                
                # Must contain both "organization" and "view"/"viewer"
                has_org = 'organization' in role_lower or 'org' in role_lower
                has_view = 'view' in role_lower or 'viewer' in role_lower
                
                # Exclude SCA, project-specific, or other specialized roles
                exclude_terms = ['sca', 'project', 'group', 'application', 'app', 'library', 'vulnerability']
                has_excluded = any(term in role_lower for term in exclude_terms)
                
                if has_org and has_view and not has_excluded:
                    print(f"    Found Organization Viewer role: {role_name} (ID: {role['id']})")
                    logging.info(f"Found Organization Viewer role: {role_name} (ID: {role['id']})")
                    return role['id']
            
            # Third, show available roles for debugging
            print("    Available roles containing 'view' or 'organization':")
            for role in roles[:20]:  # Show first 20 for debugging
                role_name = role.get('name', '')
                if 'view' in role_name.lower() or 'organization' in role_name.lower():
                    print(f"      - {role_name} (ID: {role['id']})")
            
            print("    Warning: Organization Viewer role not found")
            logging.warning("Organization Viewer role not found")
            return None
        else:
            print(f"    Error fetching roles: {response.status_code}")
            logging.error(f"Error fetching roles: {response.status_code}")
            return None
    except Exception as e:
        print(f"    Error finding Organization Viewer role: {e}")
        logging.error(f"Error finding Organization Viewer role: {e}")
        return None

def create_user_access_group(name, description, user_ids, role_ids):
    """Create a User Access Group."""
    payload = {
        'name': name,
        'description': description,
        'userIds': user_ids,
        'roleIds': role_ids
    }
    
    try:
        response = requests.post(GET_USER_ACCESS_GROUPS_ENDPOINT,
                               headers=headers,
                               data=json.dumps(payload))
        if response.status_code == 201:
            uag = response.json()
            logging.info(f"User Access Group '{name}' created successfully with ID: {uag['id']}")
            return uag
        elif response.status_code == 409:
            logging.warning(f"User Access Group '{name}' already exists")
            return None  # Could fetch existing UAG if needed
        else:
            logging.error(f"Failed to create UAG '{name}': {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating UAG {name}: {e}")
        return None

def get_user_org_role(user):
    """Determine user's organization role from their existing permissions."""
    # This is a simplified mapping - you may need to adjust based on your data structure
    roles = user.get('roles', [])
    if not roles:
        return 'view'  # Default to view if no specific role
    
    # Check for admin roles first
    for role in roles:
        role_name = role.get('name', '').lower()
        if 'admin' in role_name:
            return 'admin'
        elif 'rules' in role_name:
            return 'rules_admin'
        elif 'edit' in role_name:
            return 'edit'
    
    return 'view'  # Default fallback

def process_group_migration(group, selected_actions, selected_builtin_role_id):
    """Process a single group for RBAC migration."""
    group_name = group.get('name')
    group_id = group.get('group_id')
    users = group.get('users', [])
    applications = group.get('applications', [])
    
    print(f"\n--- Processing Group: {group_name} (ID: {group_id}) ---")
    
    # Extract application IDs - applications are nested under 'application' key
    app_ids = []
    for app_entry in applications:
        if isinstance(app_entry, dict) and 'application' in app_entry:
            app_data = app_entry['application']
            if isinstance(app_data, dict) and 'app_id' in app_data:
                app_ids.append(app_data['app_id'])
    
    if not app_ids:
        print(f"  No applications found for group '{group_name}'. Skipping.")
        return
    
    print(f"  Found {len(app_ids)} applications")
    for i, app_entry in enumerate(applications[:3]):  # Show first 3 apps
        if isinstance(app_entry, dict) and 'application' in app_entry:
            app_data = app_entry['application']
            app_name = app_data.get('name', 'Unknown')
            app_id = app_data.get('app_id', 'Unknown')
            print(f"    App {i+1}: {app_name} (ID: {app_id})")
    
    # 1. Create or verify Resource Group exists
    resource_group = find_resource_group_by_name(group_name)
    if not resource_group:
        resource_group = create_resource_group(group_name, app_ids)
    
    if not resource_group:
        print(f"  Failed to create/find resource group for '{group_name}'")
        return
    
    # 2. Create single role and UAG for this resource group
    total_users = group.get('total_users', 0)
    print(f"  Group has {total_users} total users")
    
    # Create single role with user-selected permissions
    role_name = group_name  # Role name matches group name
    role = create_role(
        name=role_name,
        description=f"Role for {group_name}",
        actions=selected_actions,
        resource_group_ids=[resource_group['id']]
    )
    
    created_role = None
    if role:
        created_role = role
        print(f"    Created role: {role_name}")
        
        # Create UAG with identical name to resource group
        uag_name = group_name  # UAG name matches resource group name exactly
        role_ids = [role['id']]
        
        # Add user-selected built-in role if specified
        if selected_builtin_role_id:
            role_ids.append(selected_builtin_role_id)
            print(f"    Adding selected built-in role to UAG")
        
        uag = create_user_access_group(
            name=uag_name,
            description=f"User access group for {group_name}",
            user_ids=[],  # Empty for now - populate later with addUserstoUAGs.py
            role_ids=role_ids
        )
        
        if uag:
            print(f"    Created UAG: {uag_name} (ready for user assignment)")
    
    # Note: Use the existing addUserstoUAGs.py script to populate this UAG with actual users
    
    return {
        'group_name': group_name,
        'resource_group': resource_group,
        'roles_created': 1 if created_role else 0,
        'users_processed': total_users
    }

def get_available_actions():
    """Fetch available actions from the API."""
    try:
        url = f"{BASE_URL}/api/v4/organizations/{ORG}/actions"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            actions = response.json()
            return actions
        else:
            print(f"Error fetching actions: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching actions: {e}")
        return []

def get_available_builtin_roles():
    """Fetch available built-in roles from the API."""
    try:
        url = f"{BASE_URL}/api/v4/organizations/{ORG}/roles?size=500"  # Get more roles
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            roles = data.get('content', [])
            
            # Look for built-in roles with common patterns
            builtin_roles = []
            for role in roles:
                role_name = role.get('name', '')
                role_lower = role_name.lower()
                
                # Common patterns for built-in roles
                builtin_patterns = [
                    'organization',
                    'viewer',
                    'view',
                    'admin',
                    'reader',
                    'observer',
                    'monitor',
                    'system',
                    'default',
                    'standard'
                ]
                
                # Check if role matches built-in patterns
                is_builtin = any(pattern in role_lower for pattern in builtin_patterns)
                
                # Also include roles that don't look like custom user-created ones
                # (custom roles often have specific naming like "MyCompany_Role" or contain underscores/dashes)
                has_custom_pattern = any(char in role_name for char in ['_', '-']) and not any(pattern in role_lower for pattern in builtin_patterns)
                
                if is_builtin or not has_custom_pattern:
                    builtin_roles.append(role)
            
            # Sort by name for easier selection
            builtin_roles.sort(key=lambda x: x.get('name', ''))
            
            print(f"Found {len(builtin_roles)} potential built-in roles out of {len(roles)} total roles")
            return builtin_roles
        else:
            print(f"Error fetching roles: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching roles: {e}")
        return []

def prompt_user_for_permissions():
    """Prompt user to choose application permissions."""
    print("\nChoose application permissions for the custom roles:")
    print("1. APPLICATION_VIEW - View applications only")
    print("2. APPLICATION_EDIT - Edit applications") 
    print("3. APPLICATION_MANAGE - Full application management")
    print("4. Custom - Choose from available actions")
    
    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        if choice == '1':
            return ['APPLICATION_VIEW']
        elif choice == '2':
            return ['APPLICATION_EDIT']
        elif choice == '3':
            return ['APPLICATION_MANAGE']
        elif choice == '4':
            return prompt_custom_actions()
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

def prompt_custom_actions():
    """Let user choose from available actions."""
    actions = get_available_actions()
    if not actions:
        print("Could not fetch available actions. Using APPLICATION_EDIT as default.")
        return ['APPLICATION_EDIT']
    
    print("\nAvailable actions:")
    app_actions = [action for action in actions if 'APPLICATION' in action.upper()]
    
    for i, action in enumerate(app_actions, 1):
        print(f"{i:2d}. {action}")
    
    print("\nEnter the numbers of actions you want (comma-separated, e.g., 1,3,5):")
    while True:
        try:
            choices = input("Your choice: ").strip()
            if not choices:
                print("Please enter at least one choice.")
                continue
            
            indices = [int(x.strip()) - 1 for x in choices.split(',')]
            selected_actions = [app_actions[i] for i in indices if 0 <= i < len(app_actions)]
            
            if selected_actions:
                return selected_actions
            else:
                print("Invalid choices. Please try again.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter numbers separated by commas.")

def prompt_user_for_builtin_role():
    """Prompt user to choose a built-in role."""
    builtin_roles = get_available_builtin_roles()
    if not builtin_roles:
        print("Could not fetch built-in roles. Skipping built-in role assignment.")
        return None
    
    print(f"\nChoose a built-in role to add to all User Access Groups:")
    print("0. None - Don't add any built-in role")
    
    # Highlight organization-related roles
    org_roles = []
    other_roles = []
    
    for role in builtin_roles:
        role_name = role.get('name', 'Unknown')
        role_lower = role_name.lower()
        if 'organization' in role_lower or 'org' in role_lower:
            org_roles.append(role)
        else:
            other_roles.append(role)
    
    # Show organization roles first
    if org_roles:
        print(f"\n--- Organization Roles (Recommended) ---")
        for i, role in enumerate(org_roles, 1):
            role_name = role.get('name', 'Unknown')
            role_desc = role.get('description', '')
            print(f"{i:2d}. {role_name}")
            if role_desc:
                print(f"     {role_desc[:100]}{'...' if len(role_desc) > 100 else ''}")
    
    # Show other roles
    if other_roles:
        start_num = len(org_roles) + 1
        print(f"\n--- Other Built-in Roles ---")
        for i, role in enumerate(other_roles, start_num):
            role_name = role.get('name', 'Unknown')
            role_desc = role.get('description', '')
            print(f"{i:2d}. {role_name}")
            if role_desc:
                print(f"     {role_desc[:80]}{'...' if len(role_desc) > 80 else ''}")
    
    # Combine all roles for selection
    all_display_roles = org_roles + other_roles
    
    while True:
        try:
            choice = input(f"\nEnter your choice (0-{len(all_display_roles)}): ").strip()
            choice_num = int(choice)
            
            if choice_num == 0:
                return None
            elif 1 <= choice_num <= len(all_display_roles):
                selected_role = all_display_roles[choice_num - 1]
                print(f"Selected: {selected_role.get('name')}")
                return selected_role.get('id')
            else:
                print(f"Invalid choice. Please enter a number between 0 and {len(all_display_roles)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    """Main migration function."""
    print("Starting RBAC Migration Process...")
    print("=" * 50)
    
    # Get user preferences
    selected_actions = prompt_custom_actions()
    selected_builtin_role_id = prompt_user_for_builtin_role()
    
    print(f"\nConfiguration:")
    print(f"  Custom role permissions: {', '.join(selected_actions)}")
    print(f"  Built-in role: {'Yes' if selected_builtin_role_id else 'None'}")
    print("=" * 50)
    
    # Fetch all groups
    groups_data = get_all_groups()
    if not groups_data:
        print("Failed to fetch groups. Exiting.")
        return
    
    # Extract groups from both custom and predefined groups
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
    
    print(f"Found {len(all_groups)} groups to process")
    
    # Debug: show first few groups
    if all_groups:
        print(f"Sample group keys: {list(all_groups[0].keys())}")
        for i, group in enumerate(all_groups[:3]):
            print(f"  Group {i+1}: {group.get('name', 'Unknown')} (ID: {group.get('group_id', 'Unknown')})")
    
    groups = all_groups
    
    results = []
    
    # Process each group
    for group in groups:
        if not group.get('readonly', False):  # Skip readonly groups
            result = process_group_migration(group, selected_actions, selected_builtin_role_id)
            if result:
                results.append(result)
    
    # Summary
    print("\n" + "=" * 50)
    print("RBAC Migration Summary:")
    print(f"Groups processed: {len(results)}")
    
    total_roles = sum(r['roles_created'] for r in results)
    total_users = sum(r['users_processed'] for r in results)
    
    print(f"Total roles created: {total_roles}")
    print(f"Total users migrated: {total_users}")
    print(f"Log file: {log_file_name}")

def cleanup_rbac_resources():
    """
    Cleanup function to remove all RBAC resources created by this script.
    Use this to back out changes during testing.
    """
    print("Starting RBAC Cleanup Process...")
    print("=" * 50)
    
    # Fetch all groups to know what we created
    groups_data = get_all_groups()
    if not groups_data:
        print("Failed to fetch groups. Exiting.")
        return
    
    # Extract all group names
    all_groups = []
    custom_groups = groups_data.get('custom_groups', {})
    if isinstance(custom_groups, dict):
        for group_list in custom_groups.values():
            if isinstance(group_list, list):
                all_groups.extend(group_list)
    
    predefined_groups = groups_data.get('predefined_groups', {})
    if isinstance(predefined_groups, dict):
        for group_list in predefined_groups.values():
            if isinstance(group_list, list):
                all_groups.extend(group_list)
    
    group_names = [group.get('name') for group in all_groups if group.get('name')]
    print(f"Found {len(group_names)} groups to check for cleanup")
    
    deleted_count = {'uags': 0, 'roles': 0, 'resource_groups': 0}
    
    for group_name in group_names:
        print(f"\nCleaning up resources for: {group_name}")
        
        # 1. Delete UAG (matching group name)
        uag_deleted = delete_user_access_group_by_name(group_name)
        if uag_deleted:
            deleted_count['uags'] += 1
            
        # 2. Delete Role (matching group name)  
        role_deleted = delete_role_by_name(group_name)
        if role_deleted:
            deleted_count['roles'] += 1
            
        # 3. Delete Resource Group (matching group name)
        rg_deleted = delete_resource_group_by_name(group_name)
        if rg_deleted:
            deleted_count['resource_groups'] += 1
    
    print("\n" + "=" * 50)
    print("Cleanup Summary:")
    print(f"User Access Groups deleted: {deleted_count['uags']}")
    print(f"Roles deleted: {deleted_count['roles']}")
    print(f"Resource Groups deleted: {deleted_count['resource_groups']}")

def delete_user_access_group_by_name(name):
    """Delete a User Access Group by name."""
    try:
        # First, find the UAG
        response = requests.get(f"{GET_USER_ACCESS_GROUPS_ENDPOINT}?nameFilter={name}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            uags = data.get('content', [])
            for uag in uags:
                if uag.get('name') == name:
                    # Delete the UAG
                    delete_response = requests.delete(f"{GET_USER_ACCESS_GROUPS_ENDPOINT}/{uag['id']}", headers=headers)
                    if delete_response.status_code == 204:
                        print(f"  ✓ Deleted UAG: {name}")
                        logging.info(f"Deleted UAG: {name} (ID: {uag['id']})")
                        return True
                    else:
                        print(f"  ✗ Failed to delete UAG {name}: {delete_response.status_code}")
                        logging.error(f"Failed to delete UAG {name}: {delete_response.status_code}")
        return False
    except Exception as e:
        print(f"  ✗ Error deleting UAG {name}: {e}")
        logging.error(f"Error deleting UAG {name}: {e}")
        return False

def delete_role_by_name(name):
    """Delete a Role by name."""
    try:
        # First, find the role
        response = requests.get(f"{GET_ROLES_ENDPOINT}?nameFilter={name}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            roles = data.get('content', [])
            for role in roles:
                if role.get('name') == name:
                    # Delete the role
                    delete_response = requests.delete(f"{GET_ROLES_ENDPOINT}/{role['id']}", headers=headers)
                    if delete_response.status_code == 204:
                        print(f"  ✓ Deleted Role: {name}")
                        logging.info(f"Deleted Role: {name} (ID: {role['id']})")
                        return True
                    else:
                        print(f"  ✗ Failed to delete Role {name}: {delete_response.status_code}")
                        logging.error(f"Failed to delete Role {name}: {delete_response.status_code}")
        return False
    except Exception as e:
        print(f"  ✗ Error deleting Role {name}: {e}")
        logging.error(f"Error deleting Role {name}: {e}")
        return False

def delete_resource_group_by_name(name):
    """Delete a Resource Group by name."""
    try:
        # First, find the resource group
        response = requests.get(f"{GET_RESOURCE_GROUPS_ENDPOINT}?nameFilter={name}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            rgs = data.get('content', [])
            for rg in rgs:
                if rg.get('name') == name:
                    # Delete the resource group
                    delete_response = requests.delete(f"{GET_RESOURCE_GROUPS_ENDPOINT}/{rg['id']}", headers=headers)
                    if delete_response.status_code == 204:
                        print(f"  ✓ Deleted Resource Group: {name}")
                        logging.info(f"Deleted Resource Group: {name} (ID: {rg['id']})")
                        return True
                    else:
                        print(f"  ✗ Failed to delete Resource Group {name}: {delete_response.status_code}")
                        logging.error(f"Failed to delete Resource Group {name}: {delete_response.status_code}")
        return False
    except Exception as e:
        print(f"  ✗ Error deleting Resource Group {name}: {e}")
        logging.error(f"Error deleting Resource Group {name}: {e}")
        return False

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        cleanup_rbac_resources()
    else:
        main()