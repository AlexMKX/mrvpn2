# MRVPN2 Quick Start Guide

This guide will help you quickly deploy MRVPN2 VPN infrastructure using the prepared templates.

## Prerequisites

- Linux servers with SSH access
- Ansible 2.9+ installed locally
- Git

## Step 1: Clone and Prepare

```bash
# Clone the repository
git clone https://github.com/your-org/mrvpn2.git
cd mrvpn2

# Copy startup templates
cp -r startup-templates/* .

# Install Ansible dependencies
ansible-galaxy collection install -r requirements.yml
```

## Step 2: Configure Your Environment

### Edit inventory.yml

```yaml
---
all:
  hosts:
    "your-main-host":
      ansible_host: "YOUR_MAIN_SERVER_IP"
      ansible_user: "root"
      ansible_private_key_file: "~/.ssh/id_rsa"
      ansible_ssh_common_args: "-o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentitiesOnly=yes -o ConnectTimeout=30"
      ansible_host_key_checking: false
      ansible_ssh_retries: 3
      ansible_python_interpreter: "/usr/bin/python3"
    "your-exit-host":
      ansible_host: "YOUR_EXIT_SERVER_IP"
      ansible_user: "root"
      ansible_private_key_file: "~/.ssh/id_rsa"
      ansible_ssh_common_args: "-o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentitiesOnly=yes -o ConnectTimeout=30"
      ansible_host_key_checking: false
      ansible_ssh_retries: 3
      ansible_python_interpreter: "/usr/bin/python3"
  children:
    entrypoints:
      hosts:
        "your-main-host":
    exitnodes:
      hosts:
        "your-exit-host":
```

### Edit mrvpn_config.yml

```yaml
---
mrvpn_config:
  entrypoint: "your-main-host"
  mrvpn_base_dir: /opt
  tunnels:
    wg_exit1:
      subnet: "10.10.10.0/24"
      hosts:
        "your-main-host":
          allowed_nets: [ 0.0.0.0/0 ]
          compose_service: firezone
          masquerade: true
          table: "off"
        "your-exit-host":
          expose: 51620
          allowed_nets: [ 0.0.0.0/0 ]
          masquerade: true
          table: "off"
  routing:
    routes:
      - interface: wg_exit1
        metric: 300
        static:
          - 0.0.0.0/0
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
    fz_server_url: "https://your-vpn.example.com"
    fz_client_subnet: 10.0.100.0/24
    fz_client_gateway: 10.0.100.1
    fz_admin: "admin@your-domain.com"
    fz_admin_password: "{{ lookup('env', 'FZ_ADMIN_PASS') }}"
    fz_wireguard_port: "51620"
    fz_client_allowed_subnets:
      - "192.168.100.0/24"
```

### Edit deployment-config.yml

```yaml
---
deployment_config:
  services:
    firezone:
      deploy: true
    wireguard:
      deploy: true
    mrvpn:
      deploy: true

  network:
    vpn_subnet: "10.0.100.0/24"
    vpn_gateway: "10.0.100.1"
    wg_port: "51620"

  docker:
    compose_version: "2.33.1"
    restart_policy: "always"

  firewall:
    enable: true
    policy: "deny"
    allowed_ports:
      - port: "22"
        proto: "tcp"
        comment: "SSH"
      - port: "443"
        proto: "tcp"
        comment: "HTTPS"
      - port: "80"
        proto: "tcp"
        comment: "HTTP"
      - port: "51620"
        proto: "udp"
        comment: "WireGuard"
    allowed_networks:
      - source: "10.0.100.0/24"
        dest: "192.168.100.0/24"
        proto: "tcp/udp"
        ports: "0-65535"
        comment: "VPN to internal network"

  monitoring:
    enable: false
    log_level: "info"
```

## Step 3: Set Environment Variables

```bash
# Required variables
export FZ_ADMIN_PASS="your_secure_password_here"
export FZ_SERVER_URL="https://your-vpn.example.com"

# Optional: OIDC configuration (skip if not needed)
export YANDEX_CLIENT_ID="your_yandex_client_id"
export YANDEX_CLIENT_SECRET="your_yandex_client_secret"
```

## Step 4: Deploy Main VPN Server

```bash
# Deploy Firezone and basic infrastructure
ansible-playbook -i inventory.yml deploy_vpn.yml
```

Wait for deployment to complete. Check the output for any errors.

## Step 5: Access Firezone Web Interface

1. Open `https://your-vpn.example.com` in your browser
2. Login with the admin credentials you set
3. Configure users and policies as needed

## Step 6: Deploy Exit Node (Optional)

If you have an exit node server, deploy it after the main server is running:

```bash
# Deploy WireGuard exit node
ansible-playbook -i inventory.yml deploy_exit_node.yml
```

## Step 7: Configure OIDC (Optional)

If you want to use external authentication providers:

```bash
# Configure Yandex OIDC
ansible-playbook -i inventory.yml configure_oidc.yml \
  -e oidc_provider=yandex \
  -e target_host=your-main-host
```

**Note:** OIDC configuration is manual and optional. If you don't need external authentication, skip this step. Firezone works perfectly with built-in user management.

## Step 8: Create Test Users

Create test VPN users through the Firezone web interface:

1. Go to Settings → Users
2. Click "Add User"
3. Enter user email
4. The user will receive an invitation email

## Step 9: Download VPN Clients

1. Users can download WireGuard clients from the Firezone web interface
2. Or use the mobile apps directly
3. All traffic will be routed through your VPN infrastructure

## Troubleshooting

### Check Service Status

```bash
# On your main server
docker ps
docker-compose ps

# Check Firezone logs
docker logs firezone-firezone-1
```

### Common Issues

1. **SSH Connection Failed**: Check your SSH key and server access
2. **Docker Installation Failed**: Ensure the server has internet access
3. **Firewall Blocks Traffic**: Check UFW rules on the server
4. **OIDC Not Working**: Verify your OIDC provider credentials

### Logs Location

- Ansible logs: Local terminal output
- Docker logs: `docker logs <container_name>`
- Firezone logs: Available in the web interface

## Next Steps

1. Configure additional users and policies
2. Set up monitoring and alerts
3. Configure backup and recovery
4. Scale with additional exit nodes if needed

## Architecture Overview

```
Main Server (your-main-host):
├── Firezone (VPN server & web interface)
├── MRVPN2 (management & routing)
├── WireGuard tunnels
└── Docker containers

Exit Node (your-exit-host):
├── WireGuard tunnel
├── Docker
└── Firewall rules
```

## Security Notes

- All sensitive data is stored in environment variables
- SSH keys are used only for deployment
- Firewall rules are automatically configured
- Docker networks are isolated
- Admin passwords should be strong and unique

## Support

For issues:
1. Check the troubleshooting section above
2. Review Ansible and Docker logs
3. Verify all environment variables are set
4. Ensure server networking is correct
