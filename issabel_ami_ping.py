# /test_ami_connection.py
# A simple, self-contained script to test the AMI connection and disconnection
# without using the IssabelAMIClient class.

import asyncio
import logging
import socket
import sys
import time

# Configure basic logging to see the output
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Configuration for the AMI ---
AMI_HOST = "5.199.164.172"
AMI_PORT = 5038
AMI_USERNAME = "admin"
AMI_SECRET = "62726Mar@"
# ---

async def test_connection():
    """
    Tests connecting and authenticating with the AMI using basic socket operations.
    """
    logging.info("Starting AMI connection test.")
    
    sock = None
    try:
        # Create a socket and connect to the AMI host and port
        logging.info(f"Attempting to connect to {AMI_HOST}:{AMI_PORT}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10) # 10-second timeout
        sock.connect((AMI_HOST, AMI_PORT))
        logging.info("✅ TCP connection successful.")

        # Read the banner
        banner = sock.recv(1024).decode('utf-8').strip()
        logging.info(f"Received banner: {banner}")

        if not banner.startswith("Asterisk Call Manager"):
            logging.error("❌ Banner not recognized. This is not an Asterisk AMI port.")
            return

        # Send the login action
        login_action = f"Action: Login\r\nUsername: {AMI_USERNAME}\r\nSecret: {AMI_SECRET}\r\n\r\n"
        sock.sendall(login_action.encode('utf-8'))
        logging.info("Sent login action. Waiting for response...")

        # Read the response
        response = sock.recv(1024).decode('utf-8').strip()
        logging.info(f"Received response: {response}")

        if "Response: Success" in response:
            logging.info("✅ Authentication successful.")
        else:
            logging.error("❌ Authentication failed. Check your username and secret.")

    except socket.timeout:
        logging.error("❌ Connection attempt timed out. Check firewall rules.")
    except socket.error as e:
        logging.error(f"❌ Socket error: {e}. Check network connectivity and server status.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if sock:
            sock.close()
            logging.info("Connection closed.")

if __name__ == "__main__":
    asyncio.run(test_connection())
