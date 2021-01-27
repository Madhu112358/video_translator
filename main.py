from google.cloud import translate
from google.cloud import storage
from datetime import datetime, date, time
from google.cloud import speech
from google.cloud import translate_v2 as translate
import moviepy.editor as mp

def process_audio(event, context):
    import tempfile
    import io
    storage_client = storage.Client()

    file = event
    bucket_name = file['bucket']
    name = file['name']
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(name)
    file_path = f"gs://{bucket_name}/{name}"
    print(f"Processing file: {file['name']} from path {file_path} ")
    inputvideo = f"{tempfile.gettempdir()}/inputvideo.mp4"
    inputaudio = f"{tempfile.gettempdir()}/inputaudio.mp3"
    blob.download_to_filename(inputvideo)
    my_clip = mp.VideoFileClip(inputvideo)
    my_clip.audio.write_audiofile(inputaudio, verbose=True)
    print("after video to audio conversion")
    output_url = transcribe_gcs(inputaudio,inputvideo)
    print(output_url)

def transcribe_gcs(audio,inputvideo):
    from google.cloud import texttospeech
    """Asynchronously transcribes the audio file specified by the gcs_uri."""
    client = speech.SpeechClient()
    audio_file = open(audio, 'rb')
    content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )
    response = client.recognize(config=config, audio=audio)
    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    speechtotext = ""
    for result in response.results:
        speechtotext = speechtotext + result.alternatives[0].transcript
    print(speechtotext)
    import six
    translate_client = translate.Client()
    result = translate_client.translate(speechtotext, target_language="ta")
    client = texttospeech.TextToSpeechClient()
    translated_text = result["translatedText"]
    # Set the text input to be synthesized
    ssml_texttospeech = "<speak>{}</speak>".format(
        translated_text.replace(".", '<break time="2s"/>')
    )
    print(ssml_texttospeech)
    synthesis_input = texttospeech.SynthesisInput(ssml=ssml_texttospeech)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ta-IN", ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
        )
    output_url = upload_audio(response,"public",inputvideo)
    return output_url    

def upload_audio(audio_response, public,inputvideo):
    now = datetime.now()
    import tempfile
    input_filename = f"{tempfile.gettempdir()}/input_{now}.mp3"
    temp_filename = f"{tempfile.gettempdir()}/temp_{now}.mp3"
    f = open(input_filename, 'wb')
    f.write(audio_response.audio_content)
    f.close()

    storage_client = storage.Client()
    output_file = f"output_{now}.mp4"
    bucket = storage_client.get_bucket("videotranslator-output")
    blob = bucket.blob(output_file)
    output_video = f"{tempfile.gettempdir()}/outputvideo.mp4"
    video_clip=mp.VideoFileClip(inputvideo)
    audio_clip=mp.AudioFileClip(input_filename)
    final_clip=video_clip.set_audio(audio_clip)
    final_clip.write_videofile(output_video,fps=60,temp_audiofile=temp_filename)
    #mp.VideoFileClip(inputvideo).write_videofile(output_video,verbose=True, audio=input_filename)
    #blob.upload_from_filename(input_filename)
    blob.upload_from_filename(output_video)
    blob.make_public()

    return blob.public_url
