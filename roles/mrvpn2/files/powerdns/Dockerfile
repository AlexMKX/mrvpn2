#FROM powerdns/pdns-recursor-50:5.0.1
FROM powerdns/pdns-recursor-53
USER root
RUN apt update && apt install -y iproute2 nftables sudo sed lua-http lua-cjson lua-posix jq
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh & \
    sed -i 's/^%sudo\sALL=(ALL:ALL) ALL/%sudo   ALL=(ALL:ALL) NOPASSWD:ALL/g'  /etc/sudoers & \
    usermod -aG sudo pdns
USER pdns
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/docker-entrypoint.sh"]
