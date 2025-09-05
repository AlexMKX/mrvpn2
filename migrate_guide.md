# MRVPN2 Migration Guide: From Master to Improved

This guide provides step-by-step instructions for migrating from the original MRVPN2 (mrvpn2-master) to the improved version (mrvpn2-improved) while preserving your existing users, tunnels, and configurations.

## Prerequisites

- **Backup Everything**: Create a complete backup of your current MRVPN2 deployment
- **Downtime Planning**: Schedule maintenance window for migration
- **Test Environment**: Consider testing migration in a staging environment first
- **Access Requirements**: SSH access to all VPN servers, Ansible control node access

## Pre-Migration Analysis

### Step 1: Inventory Your Current Setup

First, document your current MRVPN2 configuration:

```bash
# 1. Check current deployment structure
find /opt/mrvpn* -type f -name "*.yml" | head -10

# 2. Document active tunnels
# Check your current tunnels configuration file
cat /path/to/your/current/mrvpn_config.yml

# 3. List current hosts and services
ansible-inventory --list

# 4. Check Firezone users (if applicable)
# Access your Firezone admin panel and note down users
```

### Step 2: Identify Configuration Files

Locate your current configuration files:

```bash
# Common locations for MRVPN2 config files:
/opt/mrvpn2/mrvpn_config.yml
/etc/ansible/inventory.yml
/etc/ansible/group_vars/
/opt/mrvpn2/playbooks/
/opt/firezone/.env
```

## Migration Process

### Phase 1: Preparation

#### Step 1: Download Improved Version

```bash
# If you haven't already:
git clone https://github.com/your-repo/mrvpn2-improved.git
cd mrvpn2-improved
```

#### Step 2: Backup Current Configuration

```bash
# Create backup directory
BACKUP_DIR="/opt/mrvpn2-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup current configs
cp -r /opt/mrvpn2/* $BACKUP_DIR/
cp -r /etc/ansible/* $BACKUP_DIR/ansible/
cp -r /opt/firezone/.env $BACKUP_DIR/firezone-env.backup
cp -r /opt/firezone/credentials.env $BACKUP_DIR/firezone-credentials.backup

echo "Backup created at: $BACKUP_DIR"
```

### Phase 2: Configuration Migration

#### Step 1: Copy Startup Templates

```bash
# Copy all startup templates to your working directory
cp -r startup-templates/* .

# Verify files are copied
ls -la *.yml *.cfg
```

#### Step 2: Migrate Inventory Configuration

**Old format** (from your current setup):
```yaml
# Your current inventory.yml or hosts file
[entrypoints]
vpn-main ansible_host=1.2.3.4

[exitnodes]
vpn-exit ansible_host=5.6.7.8
```

**New format** (inventory.yml):
```yaml
---
all:
  hosts:
    "vpn-main":  # Replace with your actual hostname
      ansible_host: "1.2.3.4"  # Your main server IP
      ansible_user: "root"
      ansible_private_key_file: "~/.ssh/id_rsa"
      ansible_ssh_common_args: "-o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentitiesOnly=yes -o ConnectTimeout=30"
      ansible_host_key_checking: false
      ansible_ssh_retries: 3
      ansible_python_interpreter: "/usr/bin/python3"
    "vpn-exit":  # Replace with your actual hostname
      ansible_host: "5.6.7.8"  # Your exit server IP
      ansible_user: "root"
      ansible_private_key_file: "~/.ssh/id_rsa"
      ansible_ssh_common_args: "-o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentitiesOnly=yes -o ConnectTimeout=30"
      ansible_host_key_checking: false
      ansible_ssh_retries: 3
      ansible_python_interpreter: "/usr/bin/python3"
  children:
    entrypoints:
      hosts:
        "vpn-main":
    exitnodes:
      hosts:
        "vpn-exit":
```

#### Step 3: Migrate MRVPN2 Configuration

**Extract from your current config** and adapt to new format:

```yaml
# mrvpn_config.yml - Adapt this from your current setup
---
mrvpn_config:
  entrypoint: "vpn-main"  # Your main server hostname
  mrvpn_base_dir: /opt
  tunnels:
    wg_exit1:  # Rename your current tunnel name
      subnet: "10.10.10.0/24"  # Your current tunnel subnet
      hosts:
        "vpn-main":  # Your main server
          allowed_nets: [ 0.0.0.0/0 ]
          compose_service: firezone
          masquerade: true
          table: "off"
        "vpn-exit":  # Your exit server
          expose: 51620
          allowed_nets: [ 0.0.0.0/0 ]
          masquerade: true
          table: "off"
    # Add more tunnels from your current config
    wg_internal:
      subnet: "192.168.100.0/24"
      hosts:
        "vpn-main":
          allowed_nets: ["192.168.100.0/24"]
          compose_service: internal
          masquerade: false
          table: "off"

  routing:
    routes:
      - interface: wg_exit1
        metric: 300
        static:
          - 0.0.0.0/0
      - interface: _DEFAULT
        metric: 100
        domains:
          - .*\.local
    pbr_mark: 200
    table: 200
    interfaces:
      - wg-firezone
      - wg_exit1

  services:
    firezone:
      - wg-firezone
      - wg_exit1

  firezone:
    fz_server_url: "https://your-domain.com"  # From current setup
    fz_client_subnet: 10.0.100.0/24  # From current setup
    fz_client_gateway: 10.0.100.1
    fz_admin: "admin@yourdomain.com"  # From current setup
    fz_admin_password: "YOUR_CURRENT_ADMIN_PASSWORD"  # CRITICAL: Copy from current .env
    fz_wireguard_port: "51620"  # From current setup
    fz_client_allowed_subnets:
      - "192.168.100.0/24"

    # OIDC Configuration (if you have any)
    fz_oidc:
      # Copy your current OIDC settings here
```

#### Step 4: Environment Variables Setup

Create environment variables file:

```bash
# Create .env file for deployment
cat > .env << EOF
# VPN Infrastructure
VPN_MAIN_HOST=vpn-main
VPN_MAIN_IP=1.2.3.4
VPN_EXIT_HOST=vpn-exit
VPN_EXIT_IP=5.6.7.8

# Firezone Configuration
FZ_SERVER_URL=https://your-domain.com
FZ_ADMIN_EMAIL=admin@yourdomain.com
FZ_ADMIN_PASS=YOUR_CURRENT_ADMIN_PASSWORD
FZ_WIREGUARD_PORT=51620

# Ansible Configuration
ANSIBLE_USER=root

# OIDC (if applicable)
YANDEX_CLIENT_ID=your_yandex_client_id
YANDEX_CLIENT_SECRET=your_yandex_client_secret
ALLOWED_DOMAINS=["yourdomain.com"]
EOF

echo "Created .env file. Please edit with your actual values."
```

### Phase 3: Deployment Migration

#### Step 1: Update Deployment Configuration

```yaml
# deployment-config.yml
---
deployment_config:
  services:
    firezone:
      deploy: true
    wireguard:
      deploy: true
    mrvpn:
      deploy: true

  # Network configuration
  network:
    vpn_subnet: "10.0.100.0/24"  # From your current setup
    vpn_gateway: "10.0.100.1"
    wg_port: "51620"

  # Docker configuration
  docker:
    compose_version: "2.33.1"
    restart_policy: "always"

  # Firewall configuration (adapt from current)
  firewall:
    enable: true
    policy: "deny"
    allowed_ports:
      - port: "22"
        proto: "tcp"
        comment: "SSH"
      - port: "80"
        proto: "tcp"
        comment: "HTTP"
      - port: "443"
        proto: "tcp"
        comment: "HTTPS"
      - port: "51620"
        proto: "udp"
        comment: "WireGuard"
    allowed_networks:
      - source: "10.0.100.0/24"
        dest: "192.168.100.0/24"
        proto: "tcp/udp"
        ports: "0-65535"
        comment: "VPN to internal network"
```

#### Step 2: Pre-Flight Check

```bash
# Test connectivity
ansible all -m ping

# Check current services
ansible vpn-main -m shell -a "docker ps"

# Verify current Firezone status
ansible vpn-main -m shell -a "docker-compose -f /opt/firezone/docker-compose.yml ps"
```

#### Step 3: Migrate Firezone Configuration

**IMPORTANT**: Preserve existing users and settings:

```bash
# On your main VPN server:
# 1. Stop current Firezone
docker-compose -f /opt/firezone/docker-compose.yml down

# 2. Backup current database
cp -r /opt/firezone/postgres-data /opt/firezone-postgres-backup

# 3. Note current admin credentials from /opt/firezone/.env
cat /opt/firezone/.env | grep ADMIN
```

### Phase 4: Deploy Improved Version

#### Step 1: Run Deployment

```bash
# Load environment variables
source .env

# Run the main deployment playbook
ansible-playbook deploy_vpn.yml
```

#### Step 2: Verify Deployment

```bash
# Check services status
ansible vpn-main -m shell -a "docker ps"

# Verify tunnels
ansible vpn-main -m shell -a "wg show"

# Check Firezone
ansible vpn-main -m shell -a "curl -k https://localhost:443"
```

#### Step 3: Restore Users (if needed)

If users were not migrated automatically:

```bash
# Access Firezone admin panel
# Navigate to https://your-domain.com
# Check if users are present
# If not, recreate them manually or restore from backup
```

### Phase 5: Post-Migration Validation

#### Step 1: Test Connectivity

```bash
# Test VPN connectivity
# Connect a client to Firezone
# Verify routing works as expected

# Test specific routes
ansible vpn-main -m shell -a "ip route show table 200"
```

#### Step 2: Validate Configuration

```bash
# Verify all configurations match your expectations
ansible vpn-main -m shell -a "cat /opt/firezone/.env"
ansible vpn-main -m shell -a "docker-compose -f /opt/firezone/docker-compose.yml config"
```

## Troubleshooting

### Common Issues

#### 1. Users Lost After Migration
```bash
# If Firezone users disappeared:
# 1. Check database backup
# 2. Restore from backup if needed
# 3. Recreate users manually
```

#### 2. Tunnel Connection Issues
```bash
# Check tunnel status
ansible all -m shell -a "wg show"

# Verify routing tables
ansible vpn-main -m shell -a "ip route show"
ansible vpn-main -m shell -a "ip route show table 200"
```

#### 3. Service Startup Failures
```bash
# Check logs
ansible vpn-main -m shell -a "docker-compose -f /opt/firezone/docker-compose.yml logs"

# Restart services
ansible-playbook deploy_vpn.yml --tags restart
```

### Rollback Procedure

If migration fails:

```bash
# 1. Stop new services
ansible-playbook deploy_vpn.yml --tags stop

# 2. Restore from backup
cp -r $BACKUP_DIR/* /opt/mrvpn2/
cp $BACKUP_DIR/firezone-env.backup /opt/firezone/.env

# 3. Restart old services
ansible-playbook /path/to/old/playbook.yml
```

## Support

- Check the logs: `ansible-playbook deploy_vpn.yml -v`
- Review the [troubleshooting guide](docs/troubleshooting.md)
- Check GitHub issues for similar problems

## Success Checklist

- [ ] Backup created
- [ ] Configuration files migrated
- [ ] Environment variables set
- [ ] Deployment successful
- [ ] Services running
- [ ] VPN connectivity verified
- [ ] Users accessible
- [ ] Routing working
- [ ] Monitoring configured

## Next Steps

1. **Monitor**: Watch logs for 24-48 hours
2. **Optimize**: Adjust configurations as needed
3. **Document**: Update your internal documentation
4. **Backup**: Schedule regular backups of new setup

---

**Remember**: Always test in a staging environment first when possible!
