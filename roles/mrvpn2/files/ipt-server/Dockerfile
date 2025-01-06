FROM pypy:3
#RUN apk update

#RUN apk add --no-cache \
#    py3-pip \
#    python3 \
#    iptables \
#    sudo \
#    nftables \
#    websocat
RUN apt-get update && apt-get install -y \
    nftables \
    iproute2 \
    conntrack
COPY . .

RUN pip install --break-system-packages -r requirements.txt

CMD [ "pypy3", "/ipt_server.py" ]
# ENTRYPOINT ["/usr/bin/pypy3","/ipt_server.py"]
#ENTRYPOINT ["/usr/bin/python3","/ipt.py"]

