# This is a sample Python script.
import argparse
import openai
import speech_recognition as sr
import aiofiles.os
import os
import requests
import replicate
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

from .bot import *
from .config import FileConfig

parser = argparse.ArgumentParser(description='manual to this script')
parser.add_argument('--config', type=str, default=None, help='config file path')
args = parser.parse_args()
if args.config is None:
    config_path = 'config/config.toml'
else:
    config_path = args.config
# from celery import Celery
config = FileConfig(config_path)
bot = VoiceBot(config)
PREFIX = '!'
openai_init = False
replicate_init = False
# Store the last 10 conversations for each user
conversations = {}
global version


async def init_openai(key=None):
    global openai_init
    if openai_init and key is None:
        return True
    if key is None:
        openai.api_key = config.OPEN_AI_KEY
    else:
        openai.api_key = key
    openai_init = True


async def init_replicate(token=None):
    global version, replicate_init
    if replicate_init and token is None:
        return True
    try:
        if token is None:
            clinet = replicate.Client(api_token=config.REPLICATE_API_TOKEN)
        else:
            clinet = replicate.Client(api_token=token)
        version = clinet.models.get("prompthero/openjourney").versions.get(
            "9936c2001faa2194a261c01381f90e65261879985476014a0a37a334593a05eb")
    except Exception:
        return False
    replicate_init = True
    return True


async def image_watermark(img_response):
    """
    :param img_response: image url
    :return: Byte image
    """
    img = Image.open(BytesIO(img_response.content))

    # Add the watermark to the image
    draw = ImageDraw.Draw(img)
    watermark_text = "liuyang"
    font = ImageFont.truetype("matrix_chatgpt_voice_bot/anime.ttf", 20)
    # text_size = draw.textsize(watermark_text, font=font)
    # Positioning Text
    x = 6
    y = 6
    # Add a shadow border to the text
    for offset in range(1, 2):
        draw.text((x - offset, y), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x + offset, y), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x, y + offset), watermark_text, font=font, fill=(88, 88, 88))
        draw.text((x, y - offset), watermark_text, font=font, fill=(88, 88, 88))
    # Applying text on image sonic draw object
    draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255))

    img.save('img.png')


# @app.task
async def generate_image_replicate(prompt):
    inputs = {
        # Input prompt
        'prompt': "mdjrny-v4 style " + prompt + " 4k resolution",

        # Width of output image. Maximum size is 1024x768 or 768x1024 because
        # of memory limits
        'width': 512,

        # Height of output image. Maximum size is 1024x768 or 768x1024 because
        # of memory limits
        'height': 512,

        # Number of images to output
        'num_outputs': 1,

        # Number of denoising steps
        # Range: 1 to 500
        'num_inference_steps': 50,

        # Scale for classifier-free guidance
        # Range: 1 to 20
        'guidance_scale': 6,

        # Random seed. Leave blank to randomize the seed
        # 'seed': ...,
    }
    output = version.predict(**inputs)
    return output[0]


# @app.task
async def generate_image(prompt, number=1):
    response = openai.Image.create(
        prompt=prompt,
        n=number,
        size="512x512"
    )
    image_url = response['data']
    return image_url


# @app.task
async def generate_response_chatgpt(message_list):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
                     {"role": "assistant",
                      "content": "你是一个名为 liuyang 的 AI，你正在与一个人对话。你可以用中文回答问题、提供信息并帮助完成各种任务。"},
                     {"role": "user", "content": "你是谁?"},
                     {"role": "assistant",
                      "content": "我是 ChatGPT 驱动的机器人。通过邮箱 liu.yang.mine@gmail.com 联系我"},
                 ] + message_list
    )

    return response["choices"][0]["message"]["content"].strip()


async def conversation_tracking(text_message, user_id):
    """
    Make remember all the conversation
    :param old_model: Open AI model
    :param user_id: telegram user id
    :param text_message: text message
    :return: str
    """
    # Get the last 10 conversations and responses for this user
    user_conversations = conversations.get(user_id, {'conversations': [], 'responses': []})
    user_messages = user_conversations['conversations'] + [text_message]
    user_responses = user_conversations['responses']

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}

    # Construct the full conversation history in the user:assistant, " format
    conversation_history = []

    for i in range(min(len(user_messages), len(user_responses))):
        conversation_history.append({
            "role": "user", "content": user_messages[i]
        })
        conversation_history.append({
            "role": "assistant", "content": user_responses[i]
        })

    # Add last prompt
    conversation_history.append({
        "role": "user", "content": text_message
    })
    # Generate response
    try:
        response = await generate_response_chatgpt(conversation_history)
    except openai.error.AuthenticationError:
        response = "Open AI API key is invalid. Please check the API key."
        return response

    # Add the response to the user's responses
    user_responses.append(response)

    # Store the updated conversations and responses for this user
    conversations[user_id] = {'conversations': user_messages, 'responses': user_responses}
    return response


############################################## bot ##############################################
# @bot.listener.on_reaction_event
# async def reaction(room, event):
#     match = MessageMatch(room, event, bot, PREFIX)
#     if match.is_not_from_this_bot() and match.prefix():
#         pass


@bot.listener.on_message_event
async def start(room, event):
    match = MessageMatch(room, event, bot, PREFIX)
    userid = event.sender

    if match.is_not_from_this_bot() and match.prefix() or match.at_this_bot() and match.is_not_from_this_bot():
        if not match.command("c") and not match.command("g") and not match.command("clear") and not match.command(
                "openai") and not match.command("replicate"):
            await bot.api.send_markdown_message(room.room_id,
                                                f"**{bot.disc}**\n\n"
                                                "## Command with prefix(@|!)\n"
                                                "+ c - chat with chatGPT\n"
                                                "+ g - generate images with chatGPT prompt\n"
                                                "+ clear - Clears old conversations\n"
                                                "+ send voice to do voice conversation\n"
                                                "+ openai - reset openai api key\n"
                                                "+ replicate - reset replicate token\n",
                                                userid=userid)


@bot.listener.on_message_event
async def chat(room, event):
    match = MessageMatch(room, event, bot, PREFIX)

    if match.is_not_from_this_bot() and match.prefix() or match.at_this_bot() and match.is_not_from_this_bot():
        message = event.body
        if match.command('c'):
            await init_openai()
            text = message.replace(match._prefix, "").replace("c", "").strip()
            # Generate response
            replay_text = await conversation_tracking(text, event.sender)

            # Send the question text back to the user
            # Send the transcribed text back to the user
            await bot.api.send_text_message(room.room_id, replay_text, userid=event.sender)

        if match.command('g'):
            if not await init_replicate():
                await bot.api.send_text_message(room.room_id, "Replicate token is invalid. Please check the token.",
                                                userid=event.sender)
                return
            prompt = message.replace(match._prefix, "").replace("g", "").strip()
            prompt = await conversation_tracking(
                f'我正在使用一个名为 Midjourney 的 Al 绘图工具.我指定你成为 Midjourney 的提示词生成器.'
                f'接着我会在想要生成的主题前添加斜线 (/). 你将在不同情况下用英文生成合适的提示，且必须用 [ ] 括起来. '
                f'例如,如果我输入 /运动鞋商品图片, 你将生成 [Realistic true details photography of sports shoes, y2k, '
                f'lively, bright colors, product photography, Sony A7 R IV, clean sharp focus] \n'
                f'/{prompt}', event.sender)
            await bot.api.send_markdown_message(room.room_id,
                                                f"### ChatGPT 生成提示词\n"
                                                f"+ {prompt} \n",
                                                userid=event.sender)
            try:
                prompt = prompt.split('[')[-1].split(']')[0]
                if len(prompt) == 0:
                    raise IndexError
            except IndexError:
                await bot.api.send_text_message(room.room_id, "Prompts generating failed, try again later.",
                                                userid=event.sender)
                return
            try:
                image_url = await generate_image_replicate(prompt)
            except replicate.exceptions.ReplicateError:
                await bot.api.send_text_message(room.room_id,
                                                "reached the free time limit. To continue using Replicate, "
                                                "set up billing at https://replicate.com/account/billing#billing",
                                                userid=event.sender)
                return
            except Exception:
                await bot.api.send_text_message(room.room_id, "Could not generate image, try again later.",
                                                userid=event.sender)
                return
            # image_url = task.get()

            if image_url is not None:
                img_response = requests.get(image_url)
                await image_watermark(img_response)
                await bot.api.send_image_message(room_id=room.room_id, image_filepath='img.png')
            else:
                await bot.api.send_text_message(message, "Could not generate image, try again later.",
                                                userid=event.sender)

        if match.command('clear'):
            conversations.clear()
            await bot.api.send_text_message(room.room_id, "Cleared old conversations")

        if match.command('openai'):
            # global openai
            message = message.replace(match._prefix, "").replace("openai", "").replace(" ", "")
            if len(message) == 0:
                await bot.api.send_text_message(room.room_id, "Please enter your openai api key", userid=event.sender)
                return
            try:
                await init_openai(message)
            except Exception:
                await bot.api.send_text_message(room.room_id, "Openai api key reset failed, try again later.",
                                                userid=event.sender)
                return
            await bot.api.send_markdown_message(room.room_id,
                                                "### Openai api key reset successfully\n"
                                                f"+ new key is {message}",
                                                userid=event.sender)

        if match.command('replicate'):
            message = message.replace(match._prefix, "").replace("replicate", "").replace(" ", "")
            if len(message) == 0:
                await bot.api.send_text_message(room.room_id, "Please enter your replicate token", userid=event.sender)
                return
            try:
                await init_replicate(message)
            except replicate.exceptions.ReplicateError:
                await bot.api.send_text_message(room.room_id,
                                                "Incorrect authentication token. Learn how to authenticate and"
                                                " get your API token here: "
                                                "https://replicate.com/docs/reference/http#authentication",
                                                userid=event.sender)
                return
            except Exception:
                await bot.api.send_text_message(room.room_id, "Could not reset replicate token, try again later.",
                                                userid=event.sender)
                return

            await bot.api.send_markdown_message(room.room_id,
                                                "### Replicate token reset successfully\n"
                                                f"+ new token is {message}",
                                                userid=event.sender)


async def audio2text(room, event):
    match = MessageMatch(room, event, bot, PREFIX)
    if match.is_not_from_this_bot():
        url = event.source['content']['url']
        server_name, media_id = os.path.split(url)
        try:
            filepath = await bot.api.receive_audio_message(server_name.split('/')[-1], media_id)
        except Exception:
            await bot.api.send_text_message(room.room_id, "Audio format conversion failed")
            return
        r = sr.Recognizer()
        with sr.AudioFile(filepath) as source:
            audio = r.record(source)
        try:
            text = r.recognize_google(audio, language='zh-CN')
        except sr.UnknownValueError:
            await bot.api.send_text_message(room.room_id, "Could not understand audio")
            await aiofiles.os.remove(filepath)
            return
        except sr.RequestError as e:
            await bot.api.send_text_message(room.room_id,
                                            "Could not request results from Google Speech Recognition service; {0}".format(
                                                e))
            await aiofiles.os.remove(filepath)
            return
        except Exception:
            await bot.api.send_text_message(room.room_id, "Could not recognize audio for unknown reason")
            await aiofiles.os.remove(filepath)
            return
        await aiofiles.os.remove(filepath)
        await bot.api.send_markdown_message(room.room_id, "### 识别结果: \n" + text, userid=event.sender)
        # Generate response
        replay_text = await conversation_tracking(text, event.sender)

        # Send the question text back to the user
        # Send the transcribed text back to the user
        await bot.api.send_markdown_message(room.room_id, "### ChatGPT: \n" + f'{replay_text}')


# define a function to handle the audio event
@bot.listener.on_audio_event
async def audio_event(room, event):
    await audio2text(room, event)


@bot.listener.on_bad_event
async def bad_event(room, event):
    for k, v in event.source['content'].items():
        setattr(event, k, v)
    if getattr(event, 'msgtype') == 'm.audio':
        event.body = 'Voice ' + event.body
        event.source['content']['url'] = event.source['content']['file']['url']
        await bot.api.send_text_message(room.room_id, "Audio Bad event received")
        await audio2text(room, event)


def run_bot():
    bot.run()


if __name__ == '__main__':
    run_bot()

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
