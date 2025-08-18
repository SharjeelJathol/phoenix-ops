import asyncio
import logging
from config import AMI_HOST, AMI_PORT, AMI_USERNAME, AMI_SECRET

class AMIClient:
    """
    An asynchronous client to connect to the Asterisk Manager Interface,
    send commands, and receive responses.
    """
    def __init__(self, host=AMI_HOST, port=AMI_PORT, username=AMI_USERNAME, secret=AMI_SECRET):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.reader = None
        self.writer = None
        self.is_connected = False

    async def connect(self):
        """Establishes a connection and logs into the AMI."""
        if self.is_connected:
            return True
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            banner = await self.reader.readuntil(b'\r\n')
            logging.info(f"AMI Banner: {banner.decode().strip()}")

            login_action = (
                f"Action: Login\r\n"
                f"Username: {self.username}\r\n"
                f"Secret: {self.secret}\r\n"
                f"Events: off\r\n\r\n"
            )
            self.writer.write(login_action.encode())
            await self.writer.drain()

            response = await self.reader.readuntil(b'\r\n\r\n')
            if b"Authentication accepted" in response:
                logging.info("AMI authentication successful.")
                self.is_connected = True
                return True
            else:
                logging.error("AMI authentication failed.")
                await self.disconnect()
                return False
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
            logging.error(f"Failed to connect to AMI: {e}")
            return False

    async def disconnect(self):
        """Closes the connection to the AMI."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
        self.is_connected = False
        logging.info("AMI connection closed.")

    async def send_action(self, action: dict):
        """
        Sends an action to the AMI and returns the complete response.
        An action is a dictionary, e.g., {'Action': 'SIPpeers'}.
        """
        if not await self.connect():
            return "Error: Could not connect to AMI."

        import uuid
        action_id = str(uuid.uuid4())
        action['ActionID'] = action_id

        command = "".join([f"{key}: {value}\r\n" for key, value in action.items()]) + "\r\n"
        
        try:
            self.writer.write(command.encode())
            await self.writer.drain()

            response_buffer = b""
            # Read until a clear end-of-response marker is found
            while True:
                chunk = await asyncio.wait_for(self.reader.read(4096), timeout=5.0)
                if not chunk:
                    break
                response_buffer += chunk
                # These markers signify the end of a command's response
                if b"--END COMMAND--" in response_buffer or b"Event: PeerlistComplete" in response_buffer or b"Response: Goodbye" in response_buffer:
                    break
            
            return response_buffer.decode(errors='ignore')
        except (OSError, asyncio.TimeoutError) as e:
            logging.error(f"Error sending action to AMI: {e}")
            await self.disconnect()
            return f"Error: Communication failed: {e}"
        finally:
            await self.disconnect()