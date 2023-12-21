import json
import urllib.request
import os
import openai 
from pydub import AudioSegment
from pydub.playback import play
from linebot import LineBotApi
from linebot.models import AudioSendMessage
import boto3
from botocore.exceptions import ClientError

# LINE
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN'] 
LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

# GPT
openai.api_key = os.environ["Openai_ACCESS_TOKEN"] 
MAX_TOKENS = 150
MODEL_ENGINE = "gpt-3.5-turbo"


# プロンプト作成関数
def make_prompt(user_message):
    try:
        prompt_rap ='''# 命令書
                    あなたは、ラッパーです。以下の制約条件から最高の相手に感謝と愛を伝えるラップを出力してください。
                    # 制約条件
                    ・入力された文の単語/フレーズは使用すること。
                    また、各セットのラップは短くし、同じ長さに収めること。
                    絶対に英語のみで出力してはいけません
                    ・絶対に使用してはいけない表現:～だ、文末が「だ」で終わる表現
                    ・お前ん家に入ったとき
                    俺の狂いかける磁場
                    深く空気を吸った
                    ここは2人の実家
                    住む
                    君に届く生活圏
                    とりまベッドの隙間に潜った
                    あぁ残り香を吸った
                    愛の芳香剤が充満
                    吸う
                    上記例を参考に回答を構築してください。
                    ・150字以内で出力してください
                    ・私の入力した文章で使われた単語を使用してください'''

        prompt = prompt_rap + user_message    

        return prompt
    
    except Exception as e:
        raise e

# 歌詞生成関数
def make_lyrics(user_massage):
    try:
        prompt = make_prompt(user_massage)

        response = openai.ChatCompletion.create(
            model=MODEL_ENGINE,
            messages=[{"role": "user", "content": prompt}],
            max_tokens = MAX_TOKENS
        )

        print(response.__dict__)
        answer = response.__dict__["_previous"]["choices"][0]["message"]["content"]

        return answer
    
    except Exception as e:
        raise e

# 音声合成
def make_voice_file(text):
    try:
        # Pollyクライアントを作成
        polly = boto3.client("polly")
        response = polly.synthesize_speech(
            Text=text,
            Engine="neural",
            OutputFormat="mp3",
            Voiceid="Kazuha"
        )
    
        # S3クライアントを作成
        s3 = boto3.client("s3")
        s3.put_object(
            Bucket='xmas-message-rap',
            Key='reading-voice.mp3',
            Body=response['AudioStream'].read()
        )

    except Exception as e:
        raise e

# instと音声を合成する関数
def make_rap_mp3():
    try:
        s3 = boto3.client("s3")

        bucket = 'xmas-message-rap'
        inst_file_key = "Dm　BPM：84.mp3"
        voice_file_key = "reading-voice.mp3"

        inst_file = s3.get_object(Bucket=bucket, Key=inst_file_key)
        voice_file = s3.get_object(Bucket=bucket, Key=voice_file_key)

        inst_audio = AudioSegment.from_mp3(inst_file)
        voice_audio = AudioSegment.from_mp3(voice_file)
        combined_audio = inst_audio + voice_audio
        combined_file = '/tmp/combined.mp3'
        combined_audio.export(combined_file, format="mp3")

        with open(combined_file, 'rb') as data:
            s3.upload_fileobj(data, bucket, 'content.mp3')

        content_url = s3.generate_presigned_url(
            'get_object', Params={'Bucket':bucket, 'Key':'content.mp3'})

        return content_url
    
    except Exception as e:
        raise e
    
# LINEメッセージ送信
def reply_message_for_line(reply_token, original_content_url):
    try:
        LINE_BOT_API.reply_message(reply_token, AudioSendMessage(original_content_url=original_content_url, duration=30000))

    except Exception as e:
        raise e

# 実行
def lambda_handler(event, context):
    try:
        if 1:
            if event["events"][0]["message"]["type"] == "text":
                reply_token = event["events"][0]['replyToken']# リプライ用トークン
                user_message = event["events"][0]["message"]["text"]# 受信メッセージ

                if user_message is None:
                    raise Exception('Elements of the event body are not found.')

                #chatgptに歌詞を生成させる
                response_text = make_lyrics(user_message)
                print("response_text", response_text)

                # 読み上げ音声ファイルの生成
                make_voice_file(response_text)

                # 音声とinstを合成してS3にエクスポート
                original_content_url = make_rap_mp3()

                # LINEの音声メッセージを送信
                reply_message_for_line(reply_token, original_content_url)

    except Exception as e:
        return {'statusCode': 200, 'body': json.dumps(f'Exception occurred: {e}')}

    return {'statusCode': 200, 'body': json.dumps('Reply ended normally.')}