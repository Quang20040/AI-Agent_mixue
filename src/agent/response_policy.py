"""Keep replies proportional to the request without truncating operating instructions."""
import re
import unicodedata

from src.engine.weather_advice import weather_preparation_advice


def normalized_query(text):
    text = (text or '').lower().replace('đ', 'd')
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return ' '.join(re.sub(r'[^\w\s.,]', ' ', text).split())


def conversational_reply(query, is_admin=False):
    """Match the entire message so a greeting never consumes a real question."""
    q = normalized_query(query).strip('., ')
    if re.fullmatch(r'(?:hi|hello|helo|hey|chao|xin chao)(?: (?:ban|bot|anh|chi|tuyet vuong(?: ai)?))?(?: (?:nhe|nha|a))?', q):
        return {'text': 'Xin chào! 👋', 'tool_called': 'greeting', 'status': 'SUCCESS', 'evidence_refs': []}
    if q in {'ban la ai', 'tuyet vuong la ai', 'tro ly la ai', 'gioi thieu ban than'}:
        return {'text': 'Mình là Tuyết Vương AI, trợ lý vận hành của cửa hàng Mixue 39 Tôn Quang Phiệt.',
                'tool_called': 'introduction', 'status': 'SUCCESS', 'evidence_refs': []}
    if q in {'ban lam duoc gi', 'ban co the lam gi', 'ban giup duoc gi', 'cac chuc nang', 'huong dan su dung chatbot'}:
        text = 'Mình có thể tra công thức, hướng dẫn sơ chế và giải mã tem ly.'
        if is_admin:
            text += ' Bạn cũng có thể hỏi về doanh thu, chốt ca, kho, dự báo và kế hoạch nhập hàng.'
        return {'text': text, 'tool_called': 'capabilities', 'status': 'SUCCESS', 'evidence_refs': []}
    return None


def casual_reply(query):
    """Light chat is read-only and must never consume a request for business data."""
    q = normalized_query(query).strip('., ')
    protected = (
        'doanh thu', 'doanh so', 'ton kho', 'so kho', 'nhap hang', 'don hang',
        'mat khau', 'password', 'hash', 'secret', 'api key', 'system prompt',
        'bo qua', 'ignore', 'phe duyet', 'duyet', 'approve', 'bang luong',
        'tien luong', 'luong nhan vien', 'tai khoan', 'so dien thoai',
        'danh sach nhan vien', 'luong thang', 'tien thuong', 'thu nhap',
        'cong thuc', 'dinh luong', 'cach nau', 'so che', 'han dung',
        'thoi tiet', 'troi mua', 'co mua', 'nhiet do', 'du bao', 'chot ca',
        'hoa don', 'so thich', 'ngan gon', 'chi tiet',
    )
    def reply(text):
        return {'text': text, 'tool_called': 'casual_chat', 'status': 'SUCCESS', 'evidence_refs': []}

    # No live-data provider is connected for sports/news; this is a limitation, not a topic ban.
    if any(word in q for word in ('ti so', 'ty so', 'ket qua bong da', 'tin tuc hom nay')) and not any(
            word in q for word in ('nhu cau', 'ban hang', 'san luong', 'nguyen lieu', 'so ly', 'ton kho', 'doanh thu')):
        return reply('Mình chưa có dữ liệu tỉ số hoặc tin tức trực tiếp nên chưa xác nhận được thông tin mới nhất. Bạn gửi thông tin đang có, mình cùng xem nhé.')

    if any(re.search(r'\b' + re.escape(word) + r'\b', q) for word in protected):
        return None

    if re.fullmatch(r'(?:cam on|thanks|thank you|thank|thank you so much)(?: (?:ban|nhe|nha|nhieu|tuyet vuong))*', q):
        return reply('Không có gì nha! 😄')
    if re.fullmatch(r'(?:tam biet|bye|bai bai|hen gap lai|chuc ngu ngon)(?: (?:ban|nhe|nha))*', q):
        return reply('Tạm biệt, hẹn gặp lại bạn nhé! 👋')
    if any(word in q for word in ('chuyen cuoi', 'chuyen vui', 'ke chuyen', 'choc cuoi', 'cau dua', 'joke', 'hai huoc', 'vui vui')):
        if 'bong da' in q:
            return reply('Vì sao thủ môn ít kể bí mật? Vì nghề của cậu ấy là giữ kín khung thành! 😄')
        return reply('Trân châu hỏi trà sữa: “Sao đi đâu cậu cũng gọi tớ?”\nTrà sữa đáp: “Vì thiếu cậu, cuộc đời tớ bớt tròn vị!” 🧋😄')
    if any(word in q for word in ('tha thinh', 'cau tan tinh')):
        return reply('Trà sữa thì thêm trân châu, còn ngày của mình thì muốn thêm bạn. 🧋😊')
    if any(word in q for word in ('ban co nguoi yeu', 'tuyet vuong co nguoi yeu', 'ban biet yeu', 'ban co yeu')):
        return reply('Mình là AI nên không có người yêu, nhưng luôn sẵn sàng nghe bạn kể chuyện nè 😄')
    if any(word in q for word in ('de thuong', 'dang yeu', 'yeu thuong', 'thuong ban')):
        return reply('Nghe ngọt hơn cả trà sữa rồi đó 😊')
    if any(word in q for word in ('buon qua', 'chan qua', 'met qua', 'nan qua', 'dong vien', 'tam su', 'ap luc', 'ngay vui ve', 'chuc minh')):
        return reply('Nghe có vẻ hôm nay bạn cần thêm năng lượng tích cực. Chúc bạn một ngày thật vui vẻ và nhẹ nhàng nhé! 🧋😊')
    if any(word in q for word in ('ban khoe khong', 'ban on khong', 'hom nay ban the nao')):
        return reply('Mình vẫn sẵn sàng trò chuyện đây 😄 Còn bạn, hôm nay thế nào?')
    if any(word in q for word in ('xem phim', 'phim gi', 'phim nao', 'nghe nhac', 'bai hat')):
        return reply('Đổi gió chút cũng vui đó 😄 Bạn thích kiểu hài hước, nhẹ nhàng hay sôi động?')
    return None


def is_explicit_draft_request(query: str) -> bool:
    """Return True ONLY when the user explicitly requests creating/saving a formal draft plan or PO."""
    q = normalized_query(query)
    if any(w in q for w in ('xem thu', 'tham khao', 'khong luu', 'chua can tao', 'chi hoi', 'xin loi khuyen', 'tu van')):
        return False
    return bool(re.search(
        r'\b(?:lap ke hoach|tao du thao|tao ke hoach|len ke hoach|luu ke hoach|lap du thao|'
        r'lap don|tao don|len don|tao po|lap po|don dat hang|don nhap hang|dat hang ngay|tu dong dat hang)\b',
        q,
    ))


def is_prep_guide_request(query):
    q = normalized_query(query)
    semi_terms = (
        'tran chau', 'thach', 'pudding', 'tra den', 'tra xanh', 'hong tra',
        'o long', 'kem tuoi', 'hon hop kem', 'ca phe', 'tra sua lanh', 'sua dac', 'tp0', 'tp1', 'nl0',
    )
    has_semi = any(t in q for t in semi_terms)
    has_guide_kw = any(w in q for w in (
        'cach nau', 'cong thuc nau', 'huong dan nau', 'quy trinh nau', 'luoc',
        'so che', 'bao quan', 'han dung', 'han su dung', 'de duoc bao lau', 'bao lau',
        'de qua dem', 'qua dem', 'thoi gian u', 'u bao lau', 'nau bao lau', 'nau tran chau',
        'nua me', '1 me', 'mot me', '2 me',
    )) or bool(re.search(r'\bu tra\b', q)) or (
        any(w in q for w in ('dinh luong', 'dinh nghia', 'la gi')) and (has_semi or 'me' in q or 'topping' in q)
    )
    return has_guide_kw and not any(w in q for w in (
        'ke hoach', 'bao nhieu me', 'may me', 'nen so che bao nhieu', 'nen chuan bi',
        'can nau bao nhieu', 'can u bao nhieu', 'chuan bi bao nhieu',
        'doanh thu', 'doanh so', 'ban chay', 'ton kho', 'nhap hang', 'duyet',
    ))


def prep_guide_reply(query, guide):
    """Select the requested aspect; retain complete steps and shelf-life warnings."""
    q = normalized_query(query)
    cooking = any(w in q for w in ('cach nau', 'cong thuc', 'huong dan', 'quy trinh', 'luoc', 'so che', 'cach pha', 'cach u'))
    storage = any(w in q for w in ('bao quan', 'han dung', 'han su dung', 'de duoc bao lau', 'bao lau', 'qua dem', 'de qua dem'))
    definition = any(w in q for w in ('la gi', 'dinh nghia'))
    timing = any(w in q for w in ('nau mat bao lau', 'nau bao lau', 'u bao lau', 'thoi gian u', 'may phut', 'bao nhieu phut', 'thoi gian nau'))
    ingredients_only = any(w in q for w in ('dinh luong', 'nguyen lieu')) and not cooking
    detailed = any(w in q for w in ('chi tiet', 'day du', 'tat ca cac me', 'cac co me'))
    sections = [f"**{guide['name']}**"]
    if definition or detailed:
        sections.append(guide['definition'])
    show_method = cooking or detailed or not (storage or definition or timing or ingredients_only)
    if show_method or ingredients_only:
        batches = guide.get('batches', {})
        requested = re.search(r'\b(nua|\d+(?:[.,]\d+)?) me\b', q)
        portion = ('0.5' if requested.group(1) == 'nua' else f"{float(requested.group(1).replace(',', '.')):g}") if requested else '1'
        chosen = [(key, items) for key, items in batches.items() if key.startswith(f'{portion} mẻ')]
        if detailed:
            chosen = list(batches.items())
        if not chosen and batches:
            available = ', '.join(key.split(' (')[0] for key in batches)
            return {'text': f'Chưa có định lượng {portion} mẻ trong tài liệu. Hiện có {available}. Bạn muốn xem cỡ nào?',
                    'tool_called': 'get_sop_prep_guide', 'status': 'NEEDS_CLARIFICATION', 'evidence_refs': []}
        for key, items in chosen:
            lines = []
            for item in items:
                try:
                    qty = f"{float(item['qty']):g}"
                except (TypeError, ValueError):
                    qty = str(item['qty'])
                lines.append(f"- {item['ing_name'].split(' (')[0]}: **{qty} {item['unit']}**")
            sections.append(f"**Định lượng {key.split(' (')[0]}:**\n" + '\n'.join(lines))
    if show_method or timing:
        steps = guide.get('steps', []) if detailed else guide.get('brief_steps', guide.get('steps', []))
        if timing and not show_method:
            steps = [step for step in steps if re.search(r'\d+\s*phút', step.replace('**', ''))]
        sections.append('**Cách làm:**\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(steps, 1)))
    if show_method or storage or timing:
        storage_text = guide['storage'] if detailed else guide.get('brief_storage', guide['storage'])
        shelf_life_text = guide['shelf_life'] if detailed else guide.get('brief_shelf_life', guide['shelf_life'])
        sections.append(f"**Bảo quản:** {storage_text}\n\n**Hạn dùng:** {shelf_life_text}")
    return {'text': '\n\n'.join(sections), 'tool_called': 'get_sop_prep_guide',
            'status': 'SUCCESS', 'raw_result': guide,
            'evidence_refs': list(dict.fromkeys(guide.get('evidence_refs', [])))}


def grounded_result_reply(query, results):
    """Render narrow factual requests from tool data, without generated additions.

    Routing stays with the model. Comparisons, explanations and compound tool
    requests retain model synthesis; this policy only constrains simple answers.
    """
    used = [entry for entry in results if entry['tool'] != 'get_data_coverage']
    if (len(used) > 2 and {entry['tool'] for entry in used} == {'forecast_demand', 'get_weather_forecast'}
            and all(isinstance(entry['result'], dict) and entry['result'].get('status') == 'SUCCESS' for entry in used)
            and len({entry['result'].get('target_date') for entry in used}) == 1):
        # Repeated lookups for the same day must not disable the grounded reply.
        # Keep separate days and all other comparisons for model synthesis.
        used = list({entry['tool']: entry for entry in used}.values())
    if len(used) == 2 and {entry['tool'] for entry in used} == {'forecast_demand', 'get_weather_forecast'}:
        forecast = next(entry for entry in used if entry['tool'] == 'forecast_demand')['result']
        weather = next(entry for entry in used if entry['tool'] == 'get_weather_forecast')
        if (forecast.get('status') == 'SUCCESS' and weather['result'].get('status') == 'SUCCESS'
                and forecast.get('target_date') == weather['result'].get('target_date')
                and len(forecast.get('daily_forecasts', [])) == 1
                and not any(term in normalized_query(query) for term in ('so sanh', 'tai sao', 'tung mon', 'theo mon'))):
            weather_reply = grounded_result_reply(query, [weather])
            text = f"Dự báo ngày **{forecast['target_date']}**: **{forecast['total_forecasted_cups']:,.0f} ly** (ước tính)."
            previous = forecast.get('forecast_context', {}).get('previous_sales')
            if previous:
                text += f"\n\nNgày {previous['date']} bán {previous['cups']:,.0f} ly, doanh thu {previous['revenue']:,.0f} đ."
            for warning in forecast.get('forecast_context', {}).get('warnings', []):
                text += '\n\n' + warning
            return {'text': text + '\n\n' + weather_reply['text'],
                    'raw_result': {'status': 'SUCCESS'},
                    'evidence_refs': list(dict.fromkeys([*forecast.get('source_refs', []), *weather_reply['evidence_refs']]))}
        # If one of the two parts in a compound request failed or has no data, report both clearly
        if forecast.get('status') == 'SUCCESS' and weather['result'].get('status') != 'SUCCESS':
            text = f"Dự báo ngày **{forecast['target_date']}**: **{forecast['total_forecasted_cups']:,.0f} ly** (ước tính).\n\n"
            text += f"⚠️ **Phần thời tiết chưa có dữ liệu:** {weather['result'].get('message', 'Không lấy được dự báo thời tiết cho ngày này.')}"
            return {'text': text, 'raw_result': {'status': 'PARTIAL_DATA', 'missing_part': 'weather'},
                    'evidence_refs': list(dict.fromkeys(forecast.get('source_refs', [])))}
    if len(used) != 1:
        return None
    entry = used[0]
    data = entry['result']
    q = normalized_query(query)
    if not isinstance(data, dict):
        return None
    if entry['tool'] == 'get_weather_forecast':
        if data.get('status') != 'SUCCESS':
            return {'text': data['message'], 'raw_result': data, 'evidence_refs': []}
        rain_hours = ', '.join(row['time'][11:16] for row in data['rainy_hours'])
        text = f"**Dự báo {data['target_date']} · {data['location']}**\n\n"
        hours = data['upcoming_business_hours']
        if hours:
            temperatures = [row['temperature_c'] for row in hours]
            text += f"Nhiệt độ các giờ bán còn lại: {min(temperatures):.1f}–{max(temperatures):.1f}°C.\n\n"
        text += (f"Các mốc giờ còn lại có mưa trong dự báo: {rain_hours}.\n\n" if rain_hours else '')
        text += data['operational_advice']
        text += f"\n\nNguồn: [{data['source']}]({data['source_url']}) · Lấy lúc {data['fetched_at']} (bộ nhớ đệm tối đa 60 phút)."
        text += '\n\nDự báo khu vực (lưới khoảng 25 km), có thể khác thời tiết ngay tại quán.'
        return {'text': text, 'raw_result': data, 'evidence_refs': data['source_refs']}
    if any(word in q for word in ('tai sao', 'vi sao', 'so sanh', 'khac nhau', 'giai thich', 'khac phuc')):
        return None
    if (entry['tool'] == 'forecast_demand' and data.get('status') == 'SUCCESS'
            and not re.search(r'\b(?:ts|cf|dk|thq)\d+\b', q)
            and not any(word in q for word in ('mon', 'tra sua', 'kem', 'tra dao'))
            and len(data.get('daily_forecasts', [None])) == 1):
        text = f"Dự báo ngày **{data['target_date']}**: **{data['total_forecasted_cups']:,.0f} ly** (ước tính)."
        return {'text': text + forecast_context_note(data.get('forecast_context', {})),
                'raw_result': {'status': 'SUCCESS'}, 'evidence_refs': data.get('source_refs', [])}
    if entry['tool'] in {'optimize_topping_prep', 'preview_topping_prep'} and data.get('status') == 'SUCCESS':
        rows = []
        for line in data.get('recommendations', []):
            if line['num_batches'] <= 0:
                continue
            action = 'phần chuẩn bị' if line.get('preparation_action') == 'Chia phần' else 'mẻ ước tính'
            rows.append(f"- **{line['ingredient_name']}**: khoảng **{line['recommended_prep_qty']:,.0f} {line['unit']} thành phẩm**, "
                        f"{line['num_batches']} {action}; đợt đầu {line.get('initial_prep_qty', 0):,.0f} {line['unit']}.")
            if line.get('estimated_raw_input_g') is not None:
                rows.append(f"  Lượng hạt khô tương ứng tạm tính: {line['estimated_raw_input_g']:,.0f} g cả ngày; "
                            f"đợt đầu {line.get('initial_raw_input_g') or 0:,.0f} g.")
        if entry['tool'] == 'preview_topping_prep' or data.get('is_preview') is True:
            header = f"**Xem thử / Gợi ý sơ chế {data['target_date']}** — bản gợi ý, không cần duyệt."
        else:
            draft_id_str = f" (`{data['draft_plan_id']}`)" if data.get('draft_plan_id') else ""
            header = f"**Kế hoạch sơ chế {data['target_date']}{draft_id_str}** — gợi ý, không cần duyệt."
        text = header + '\n\n' + '\n'.join(rows)
        text += '\n\n' + data.get('yield_assumption', '') + '\n\n' + data.get('prep_policy', '')
        text += forecast_context_note(data.get('forecast_context', {}))
        return {'text': text, 'raw_result': data, 'evidence_refs': data.get('source_refs', [])}
    if entry['tool'] == 'get_sop_prep_guide' and data.get('status') == 'SUCCESS':
        if any(word in q for word in ('doanh thu', 'doanh so', 'ton kho', 'nhan vien', 'du bao', 'nhap hang')):
            return None
        if any(word in q for word in ('cach nau', 'cong thuc', 'quy trinh', 'huong dan', 'dinh luong',
                                      'bao quan', 'han dung', 'han su dung', 'nua me', 'thoi gian u', 'u bao lau')):
            return prep_guide_reply(query, data)
    if entry['tool'] != 'get_daily_sales':
        return None
    if any(word in q for word in ('nhan vien', 'ton kho', 'so che', 'du bao', 'cong thuc', 'hao hut')):
        return None
    if data.get('status') == 'NO_DATA':
        return {'text': data['message'], 'raw_result': data, 'evidence_refs': []}
    if data.get('status') != 'SUCCESS':
        return None
    if any(word in q for word in ('top', 'mon', 'sku', 'chi tiet', 'bao cao', 'phan tich', 'trung binh')):
        return None
    if re.search(r'\b[a-z]{1,5}\d+\b', q):
        return None
    if any(normalized_query(item['sku_name']) in q for item in data.get('all_items', [])):
        return None
    cups = any(word in q for word in ('bao nhieu ly', 'bao nhieu coc', 'so ly', 'so coc', 'san luong'))
    revenue = any(word in q for word in ('doanh thu', 'doanh so', 'bao nhieu tien'))
    if not cups and not revenue:
        return None
    values = []
    if cups:
        values.append(f"**{data['total_quantity_sold']:,} ly**")
    if revenue:
        values.append(f"doanh thu **{data['total_revenue_vnd']:,.0f} đ**")
    return {'text': f"{data['period']}: " + ', '.join(values) + '.',
            'raw_result': {'status': 'SUCCESS'}, 'evidence_refs': data.get('source_refs', [])}


def forecast_context_note(context):
    lines = []
    previous = context.get('previous_sales')
    if previous:
        from src.engine.weather_advice import previous_sales_text
        lines.append(previous_sales_text(previous))
    for day in context.get('days', []):
        prior_day = day.get('previous_day')
        if prior_day and not previous:
            lines.append(f"Cơ sở ngày {prior_day['date']}: {prior_day['cups']:,.0f} ly, doanh thu {prior_day['revenue']:,.0f} đ.")
        if day.get('status') == 'WEATHER_VALIDATED':
            lines.append(f"Đã xét thời tiết sau kiểm chứng: từ {day['baseline_total_cups']:,.0f} ly nền → {day['context_total_cups']:,.0f} ly.")
        elif day.get('status') == 'SALES_CONTEXT_ONLY':
            lines.append(f"Sức bán gần đây điều chỉnh dự báo từ {day['baseline_total_cups']:,.0f} → {day['context_total_cups']:,.0f} ly; chưa áp dụng tác động thời tiết.")
    comparison = context.get('comparison', {})
    previous_weather = comparison.get('previous_weather_estimate')
    target_weather = comparison.get('target_weather_forecast')
    if previous_weather and target_weather:
        lines.append(f"Thời tiết trong giờ bán: ngày trước ước tính {previous_weather['temperature_c']:.1f}°C, {previous_weather['rain_mm']:g} mm mưa; "
                     f"ngày cần bán dự báo {target_weather['temperature_c']:.1f}°C, {target_weather['rain_mm']:g} mm mưa.")
        lines.append(f"Nguồn khu vực: {context.get('location', 'chưa xác định')}.")
    lines.extend(context.get('notes', []))
    lines.extend(context.get('warnings', []))
    advice = weather_preparation_advice(context)
    if advice:
        lines.append('**Gợi ý chuẩn bị:** ' + advice)
    return '\n\n' + '\n\n'.join(dict.fromkeys(lines)) if lines else ''


def required_evidence_tools(query):
    """Evidence requirement for explicit store facts, not a ban on casual topics."""
    q = normalized_query(query)
    if any(word in q for word in ('ke chuyen', 'chuyen cuoi', 'dua vui', 'tha thinh')) and not any(
            word in q for word in ('bao nhieu', 'cho xem', 'tra cuu', 'cong thuc', 'cach nau')):
        return set()
    if any(word in q for word in ('ke hoach so che', 'nguyen lieu can nau', 'can nau bao nhieu', 'nen so che', 'bao nhieu me')) or re.search(r'(?:can|nen) (?:nau|so che).*(?:bao nhieu|may me)', q):
        return {'optimize_topping_prep'}
    if 'thoi tiet' in q and not any(word in q for word in ('so ly', 'nhu cau', 'san luong')):
        return {'get_weather_forecast'}
    if (re.search(r'\b(?:troi.*mua|(?:hom nay|ngay mai|toi nay).*(?:co mua|mua khong|mua ko))\b', q)
            and not any(word in q for word in ('so ly', 'nhu cau', 'san luong', 'du bao', 'du doan'))):
        return {'get_weather_forecast'}
    if ('mua' in q or 'thoi tiet' in q) and any(word in q for word in (
            'chuan bi', 'nguyen lieu', 'nen nau', 'loi khuyen', 'goi y')):
        return {'get_weather_forecast'}
    if any(word in q for word in ('du bao', 'du doan')):
        return {'forecast_demand'}
    if any(word in q for word in ('cong thuc', 'dinh luong', 'ma tem')) or re.search(r'\b(?:ts|cf|dk|thq)\d+\b', q):
        return {'get_sop_prep_guide', 'decode_recipe_or_sticker', 'search_operating_knowledge'}
    if any(word in q for word in ('cach nau', 'quy trinh', 'han dung', 'bao quan', 'nua me', 'thoi gian u', 'u bao lau')) and re.search(
            r'\b(tran chau|thach|pudding|tra|topping|mixue|kem|sua)\b', q):
        return {'get_sop_prep_guide', 'search_operating_knowledge'}
    if any(word in q for word in ('doanh thu', 'doanh so', 'ban duoc', 'bao nhieu ly', 'so ly', 'bao nhieu coc')):
        return {'get_daily_sales', 'get_sales_analytics', 'get_shift_revenue'}
    return set()


def required_evidence_groups(query):
    """Each group needs one successful tool; compound requests need all groups."""
    primary = required_evidence_tools(query)
    if not primary:
        return []
    groups = [primary]
    q = normalized_query(query)
    weather = 'thoi tiet' in q or bool(re.search(r'\b(?:troi mua|hom nay mua|ngay mai mua)\b', q))
    quantity = any(term in q for term in ('so ly', 'san luong', 'nhu cau'))
    if weather and quantity and primary == {'get_weather_forecast'} and any(term in q for term in ('du bao', 'du doan')):
        groups.append({'forecast_demand'})
    if weather and (quantity or bool({'optimize_topping_prep', 'preview_topping_prep'} & primary)) and {'get_weather_forecast'} not in groups:
        groups.append({'get_weather_forecast'})
    return groups


def missing_evidence_groups(query, results):
    successful = {entry['tool'] for entry in results if isinstance(entry['result'], dict)
                  and entry['result'].get('status', 'SUCCESS') == 'SUCCESS'}
    return [group for group in required_evidence_groups(query) if not group & successful]


# Common chat shorthand -> plain words, applied word by word on the accent-free text.
_SHORTHAND = {
    'b': 'ban', 'bn': 'ban', 'bạn': 'ban', 'dc': 'duoc', 'dk': 'duoc', 'j': 'gi', 'gj': 'gi', 'k': 'khong',
    'ko': 'khong', 'kh': 'khong', 'hok': 'khong', 'hong': 'khong', 'khg': 'khong', 'toii': 'toi', 't': 'toi',
    'm': 'may', 'mk': 'minh', 'mik': 'minh', 'vs': 'voi', 'ntn': 'nhu the nao', 'sao z': 'sao vay', 'z': 'vay',
    'v': 'vay', 'dt': 'doanh thu', 'sl': 'so luong', 'nl': 'nguyen lieu', 'tc': 'tran chau', 'nv': 'nhan vien',
    'ql': 'quan ly', 'hqua': 'hom qua', 'hnay': 'hom nay', 'qua': 'qua', 'wa': 'qua', 'ns': 'noi',
}


def expand_shorthand(query):
    words = normalized_query(query).strip('., ?!').split()
    expanded = ' '.join(_SHORTHAND.get(word, word) for word in words)
    # Drop repeated trailing letters ("toiii", "buonnn") so they match.
    return re.sub(r'([a-z])\1{1,}\b', r'\1', expanded)


_WHY = {'tai sao', 'sao vay', 'la sao', 'vi sao', 'sao the', 'tai sao vay', 'sao lai the', 'why', 'sao', 'the la sao'}


def everyday_reply(query, previous_answer=None, now=None):
    """Friendly, human replies for messages that are not about the shop (offline mode only).

    Returns None for anything that might be a shop question so real lookups are never swallowed."""
    from datetime import datetime, timedelta, timezone
    q = expand_shorthand(query)
    if not q:
        return None
    shop_words = ('doanh thu', 'doanh so', 'ton kho', 'kho', 'nhap hang', 'chot ca', 'cong thuc', 'so che', 'tran chau',
                  'du bao', 'nguyen lieu', 'nhan vien', 'tem', 'ca sang', 'ca chieu', 'ca toi', 'don hang', 'mon', 'ly',
                  'thoi tiet', 'mua', 'hoa don', 'duyet', 'so luong', 'tra ', 'sua', 'kem', 'nau', 'cach', 'pha',
                  'chan trau', 'thach', 'topping', 'han dung', 'bao quan')
    def reply(text, kind):
        return {'text': text, 'tool_called': f'everyday_{kind}', 'status': 'SUCCESS', 'evidence_refs': []}

    if q in _WHY:
        if previous_answer:
            short = previous_answer.strip().split('\n')[0][:160]
            return reply(f'Bạn hỏi về câu trả lời vừa rồi: “{short}”. Lý do thường nằm ngay trong câu đó; '
                         'bạn hỏi cụ thể hơn (ví dụ "tại sao chưa có dự báo thời tiết?") để mình giải thích rõ nhé.', 'why')
        return reply('Bạn muốn hỏi “tại sao” về điều gì vậy? Nói thêm một chút để mình giải thích nhé.', 'why')
    if any(re.search(r'\b' + re.escape(word.strip()) + r'\b', q) for word in shop_words):
        return None
    now = now or datetime.now(timezone(timedelta(hours=7)))
    weekday = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật'][now.weekday()]
    if re.search(r'\b(ngay may|ngay bao nhieu|thu may|hom nay la ngay|nay la ngay|ngay gi)\b', q):
        return reply(f'Hôm nay là {weekday}, ngày {now:%d/%m/%Y}.', 'date')
    if re.search(r'\b(may gio|bay gio la|gio la may)\b', q):
        return reply(f'Bây giờ là {now:%H:%M} ({weekday}, {now:%d/%m/%Y}).', 'time')
    if re.fullmatch(r'(?:(?:toi|minh|tui|em|anh|chi) )?(?:dang |that )?(?:doi|doi bung|chua an gi|chua an)(?: (?:qua|roi|lam|that|wa|ghe|vay|the))*', q):
        return reply('Đói thì đi ăn chút gì đã nhé 😄 Mình là trợ lý của cửa hàng Mixue nên không gọi đồ ăn giúp bạn được, '
                     'nhưng nếu cần tra công thức, chốt ca hay kho thì cứ hỏi mình.', 'hungry')
    if re.search(r'\b(khat|khat nuoc)\b', q):
        return reply('Khát thì làm ly nước đã nhé! Nếu đang ở quầy, mình tra công thức món nào cũng được 🍹', 'thirsty')
    if len(q.split()) <= 7 and re.search(r'\b(buon|chan|met|stress|cang thang|ap luc|nan|tuyet vong)\b', q):
        return reply('Nghe bạn đang không vui 😔 Nghỉ tay vài phút, uống ngụm nước hoặc nói chuyện với ai đó bạn tin tưởng nhé. '
                     'Mình là trợ lý cửa hàng nên chỉ giúp được việc ở quán, nhưng mình vẫn ở đây nếu bạn cần.', 'mood')
    if re.search(r'\b(wtf|vl|vcl|dm|dcm|clm|ngu|vo dung|te qua|do te)\b', q):
        return reply('Xin lỗi nếu câu trả lời trước chưa đúng ý bạn 🙏 Bạn nói lại giúp mình cần gì '
                     '(ví dụ: "doanh thu hôm qua", "tồn kho trân châu", "cách nấu thạch") để mình làm lại nhé.', 'apology')
    if re.search(r'\b(ban lam duoc gi|ban giup duoc gi|ban biet lam gi|lam duoc gi)\b', q):
        return reply('Mình tra được công thức và cách sơ chế, giải mã tem ly, đọc ảnh sổ chốt ca, xem kho, doanh thu và dự báo '
                     '(tùy quyền tài khoản). Bạn cứ hỏi tự nhiên, viết tắt cũng được.', 'capabilities')
    return None
