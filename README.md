# Contrast Security RBAC Migration Toolkit

A comprehensive Python toolkit for migrating from Contrast Security's EAC (Existing Access Control) to RBAC (Role-Based Access Control) with interactive configuration and automated cleanup capabilities.

## Features

- **Interactive RBAC Migration** - Choose permissions and built-in roles during migration
- **Automated Resource Creation** - Creates Resource Groups, Roles, and User Access Groups with matching names
- **Centralized Configuration** - Single `.env` file for all credentials and settings
- **Comprehensive Logging** - Detailed audit logs for all operations
- **Easy Cleanup** - Built-in rollback functionality for testing
- **User Migration Support** - Tools to migrate users from existing groups to new UAGs

## Project Structure

```
├── rbac_migration.py      # Main interactive RBAC migration script
├── addUserstoUAGs.py      # Migrate users from groups to UAGs
├── config_loader.py       # Configuration utility
├── .env                   # Environment configuration
└── Results/               # Output files directory
```

## Prerequisites

- Python 3.6+ (Python 3.13+ recommended)
- Contrast Security API credentials
- Organization UUID and appropriate permissions

## Quick Setup

1. **Clone and setup the project:**
   ```bash
   git clone https://github.com/marklacasse/rbac_migration.git
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure credentials in `.env` file:**
   ```env
   API_KEY=your_api_key_here
   BASE_URL=https://your-contrast-server.com/
   AUTH=your_base64_encoded_authorization_header
   ORG=your_organization_uuid
   LOG_DIR=Results
   ```

3. **Run the interactive migration:**
   ```bash
   python3 rbac_migration.py
   ```

## Main Migration Workflow

### Step 1: Interactive RBAC Migration

The `rbac_migration.py` script provides an interactive migration experience that transforms your existing EAC groups into a complete RBAC structure:

```bash
python3 rbac_migration.py
```

#### How the Migration Works

**Input: Existing Groups**

The script discovers all non-readonly groups in your Contrast organization, including:

- Custom groups created for specific applications or teams
- Predefined groups with existing permissions

**Output: Complete RBAC Structure**
For each existing group, the script creates a complete RBAC hierarchy:

1. **Resource Group** - Container for applications with the same name as the original group
   - Name: `{original_group_name}`
   - Contains applications that were accessible to the original group

2. **Role** - Defines permissions with your selected APPLICATION action
   - Name: `{original_group_name}`
   - Permissions: Your chosen APPLICATION action (VIEW, EDIT, MANAGE, etc.)
   - Scope: Limited to the matching Resource Group

3. **User Access Group (UAG)** - Combines the role with organization-level permissions
   - Name: `{original_group_name}`
   - Role Assignment: The newly created role (application permissions)
   - Built-in Role: Your selected organization role (ORGANIZATION_VIEW_ROLE, etc.)
   - Ready to receive users from the original group

#### Interactive Configuration

**What it does:**

1. **Interactive Permission Selection** - Choose from available APPLICATION actions (VIEW, EDIT, MANAGE, etc.)
2. **Built-in Role Selection** - Select organization-level roles (Organization Viewer, etc.)
3. **Automated Resource Creation** - Creates matching Resource Groups, Roles, and UAGs
4. **Exact Name Matching** - Ensures consistent naming across all RBAC components

#### Migration Example

If you have an existing group called "DevTeam-WebApp":

```text
Original Group: "DevTeam-WebApp"
├── Had access to specific applications
└── Contains user memberships

Creates RBAC Structure:
├── Resource Group: "DevTeam-WebApp"
│   └── Contains the same applications
├── Role: "DevTeam-WebApp" 
│   └── APPLICATION_EDIT permissions on Resource Group
└── User Access Group: "DevTeam-WebApp"
    ├── Assigned Role: "DevTeam-WebApp"
    ├── Built-in Role: "ORGANIZATION_VIEW_ROLE"
    └── Ready for user migration
```

**Example Output:**
```
Available actions:
 1. APPLICATION_ADMIN
 2. APPLICATION_EDIT
 3. APPLICATION_VIEW
Your choice: 2

Choose a built-in role:
--- Organization Roles (Recommended) ---
 1. ORGANIZATION_VIEW_ROLE
 2. ORGANIZATION_EDIT_ROLE
Your choice: 1

✓ Created 6 roles with APPLICATION_EDIT permissions
✓ Created 6 UAGs with Organization View role
```

### Step 2: Migrate Users (Optional)

After creating the RBAC structure, migrate users:

> **Warning:**
This step isn’t required if SSO/SAML is configured for `contrast_groups`. When users log in, they’ll automatically be added to their appropriate groups. For more details, see [Auto-add users](https://docs.contrastsecurity.com/en/auto-add-users.html).


```bash
python3 addUserstoUAGs.py
```

### Step 3: Cleanup/Testing

For testing or rollback purposes:

```bash
python3 rbac_migration.py cleanup
```

## 🔧 Configuration Details

### Environment Variables (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `API_KEY` | Contrast Security API key | `abcd1234...` |
| `BASE_URL` | Contrast server URL | `https://app.contrastsecurity.com/` |
| `AUTH` | Base64 encoded credentials | `dXNlcm5hbWU6cGFzc3dvcmQ=` |
| `ORG` | Organization UUID | `12345678-1234-...` |
| `LOG_DIR` | Directory for log files | `Results` (default) |

### Getting Your Credentials

1. **API Key**: User Settings → Profile → API Key
2. **AUTH**: Base64 encode your `username:service_key`
3. **ORG**: Organization Settings → Organization UUID
4. **BASE_URL**: Your Contrast server URL

## 📊 Logging and Auditing

All operations are logged to `{LOG_DIR}/rbac_migration_logs_YYYY-MM-DD.txt` with:

- Timestamp for each operation
- Success/failure status
- Resource IDs created
- Error details for troubleshooting

## Troubleshooting

### Common Issues

1. **Import Error (requests)**

   ```bash
   # Ensure you're using the virtual environment
   source .venv/bin/activate
   pip install requests
   ```

2. **API Authentication Errors**
   - Verify API key and AUTH credentials in `.env`
   - Check organization UUID is correct
   - Ensure API key has required permissions

3. **Organization Viewer Role Not Found**
   - The script now automatically detects available roles
   - Check the "Organization Roles" section in the interactive prompt

### Log Analysis

Check `{LOG_DIR}/rbac_migration_logs_*.txt` for detailed error information:

```bash
tail -f Results/rbac_migration_logs_$(date +%Y-%m-%d).txt
```

## Script Reference

### Primary Scripts

- **`rbac_migration.py`** - Main interactive migration with cleanup
- **`addUserstoUAGs.py`** - User migration utility
- **`config_loader.py`** - Configuration management utility
