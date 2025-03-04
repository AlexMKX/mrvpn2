FROM python:3.12-alpine

RUN apk add --no-cache \
    nftables \
    iproute2 \
    conntrack-tools \
    sudo

# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --break-system-packages -r requirements.txt

# Copy the rest of the application
COPY . .

CMD [ "python3", "/ipt_server.py" ]

