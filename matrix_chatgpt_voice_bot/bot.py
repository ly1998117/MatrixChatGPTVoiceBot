import aiofiles.os
import markdown
from simplematrixbotlib import Bot, Creds, Api
import simplematrixbotlib.match as match
from pydub import AudioSegment
from nio import RoomMessageText, UnknownEvent, RoomMessageAudio, RoomMessageImage


class MessageMatch(match.MessageMatch):
    def at_this_bot(self):
        if hasattr(self.event, 'formatted_body') and self.event.formatted_body is not None and \
                self._bot.creds.username in self.event.formatted_body:
            self.event.body = self.event.body.replace(f'{self._bot.username}:', '')
            return True
        return False


class MediaApi(Api):
    def __init__(self, creds, config):
        super().__init__(creds, config)
        self.username = self.creds.username

    async def receive_audio_message(self, server_name, media_id):
        response = await self.async_client.download(server_name, media_id)
        # first do an upload of image, then send URI of upload to room
        async with aiofiles.open(response.filename, "wb") as f:
            await f.write(response.body)
        sound = AudioSegment.from_file(response.filename)

        filepath = response.filename.split('.')[0] + '.wav'
        sound.export(filepath, format="wav")
        await aiofiles.os.remove(response.filename)
        return filepath

    async def content_format(self, message, userid, msgtype, message_format_fn=lambda x: x):
        content = {
            'body': message,
            'msgtype': msgtype,
        }
        if userid:
            content.update({
                'format': 'org.matrix.custom.html',
                'formatted_body': f'<a href="https://matrix.to/#/{userid}">{self.username}</a>: {message_format_fn(message)}'
            })
        else:
            content.update({
                'format': 'org.matrix.custom.html',
                'formatted_body': f'{message_format_fn(message)}'
            })
        return content

    async def send_text_message(self, room_id, message, msgtype='m.text', userid=None):
        """
        Send a text message in a Matrix room.

        Parameteres
        -----------
        room_id : str
            The room id of the destination of the message.

        message : str
            The content of the message to be sent.

        msgtype : str, optional
            The type of message to send: m.text (default), m.notice, etc

        """

        content = await self.content_format(message, userid, msgtype)
        await self._send_room(room_id=room_id,
                              content=content)

    async def send_markdown_message(self, room_id, message, msgtype='m.text', userid=None):
        """
        Send a markdown message in a Matrix room.

        Parameteres
        -----------
        room_id : str
            The room id of the destination of the message.

        message : str
            The content of the message to be sent.

        msgtype : str, optional
            The type of message to send: m.text (default), m.notice, etc

        """

        content = await self.content_format(message, userid, msgtype,
                                            lambda x: markdown.markdown(x, extensions=['nl2br']))

        await self._send_room(room_id=room_id, content=content)


class Listener:

    def __init__(self, bot):
        self._bot = bot
        self._registry = []
        self._startup_registry = []

    def on_custom_event(self, event):

        def wrapper(func):
            if [func, event] in self._registry:
                func()
            else:
                self._registry.append([func, event])

        return wrapper

    def on_message_event(self, func):
        if [func, RoomMessageText] in self._registry:
            func()
        else:
            self._registry.append([func, RoomMessageText])

    def on_audio_event(self, func):
        if [func, RoomMessageAudio] in self._registry:
            func()
        else:
            self._registry.append([func, RoomMessageAudio])

    def on_image_event(self, func):
        if [func, RoomMessageImage] in self._registry:
            func()
        else:
            self._registry.append([func, RoomMessageImage])

    def on_reaction_event(self, func):

        async def new_func(room, event):
            if event.type == "m.reaction":
                await func(room, event,
                           event.source['content']['m.relates_to']['key'])

        self._registry.append([new_func, UnknownEvent])

    def on_startup(self, func):
        if func in self._startup_registry:
            func()
        else:
            self._startup_registry.append(func)


class VoiceBot(Bot):
    def __init__(self, config):
        creds = Creds(homeserver=config.HOMESERVER,
                      username=config.USERNAME,
                      password=config.PASSWORD,
                      login_token=config.LOGIN_TOKEN,
                      access_token=config.ACCESS_TOKEN)
        super().__init__(creds, config)
        self.listener = Listener(self)
        self.api = MediaApi(self.creds, self.config)
        self.username = self.creds.username
        self.disc = config.DESCRIPTION
