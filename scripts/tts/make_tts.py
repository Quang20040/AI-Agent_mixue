"""Synthesize the demo narration with edge-tts (several voices) into tts_out/<voice>/NN.mp3."""
import asyncio, json, sys
from pathlib import Path
import edge_tts

VOICES = {  # voice: (text field, rate, pitch)
    'vi-VN-HoaiMyNeural': ('resp', '+6%', '+4Hz'),
    'vi-VN-NamMinhNeural': ('resp', '+6%', '+0Hz'),
    'en-US-AndrewMultilingualNeural': ('orig', '+0%', '+0Hz'),
    'en-US-AvaMultilingualNeural': ('orig', '+0%', '+0Hz'),
}
SAMPLE = 'Khi duyệt, đồ thị {LangGraph} dừng lại ở bước {interrupt}; {Gemini} chỉ chép nguyên văn từng ô trên phiếu {POS}.'


async def main(out):
    lines = json.load(open(Path(__file__).with_name('narration.json')))
    resp = {'LangGraph': 'Lăng-gráp', 'interrupt': 'in-tơ-rắp', 'Gemini': 'Giê-mi-nai', 'POS': 'pốt'}
    for voice, (field, rate, pitch) in VOICES.items():
        d = Path(out) / voice
        d.mkdir(parents=True, exist_ok=True)
        for i, line in enumerate(lines):
            await edge_tts.Communicate(line[field], voice, rate=rate, pitch=pitch).save(str(d / f'{i:02d}.mp3'))
        text = SAMPLE
        for k, v in resp.items():
            text = text.replace('{%s}' % k, v if field == 'resp' else k)
        await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(d / 'sample.mp3'))
        print(voice, 'ok', flush=True)

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else 'tts_out'))
