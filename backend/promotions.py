"""
promotions.py - Multilingual Promotional Offer & WhatsApp Alert Generator
Part of BiscuitAI (Chunk 1)

Mental Model:
Generates targeted WhatsApp/SMS alert messages in English, Bengali, and Hindi
for FMCG distributors to send to retail stores.
Tailored to festival occasions and specific SKU overstock or festive surges.
Zero third-party API dependencies ($0.00 cost, instantaneous generation).
"""

from typing import Dict

PROMOTION_TEMPLATES = {
    "DURGA_PUJA": {
        "en": "🎉 Festive Alert! Durga Puja demand is surging. Order {cartons} cartons of {sku_name} before {cutoff_day} and get an extra {discount}% distributor margin. Stock arriving in 24 hrs. Reply YES to confirm.",
        "bn": "🎉 উৎসবের অফার! দুর্গাপূজার জন্য {sku_name}-এর ব্যাপক চাহিদা। {cutoff_day}-এর মধ্যে {cartons} কার্টুন অর্ডার করলে অতিরিক্ত {discount}% ছাড় পান। ডেলিভারি ২৪ ঘণ্টার মধ্যে। কনফার্ম করতে YES লিখুন।",
        "hi": "🎉 त्योहार स्पेशल! दुर्गा पूजा के लिए {sku_name} की भारी मांग। {cutoff_day} से पहले {cartons} कार्टन ऑर्डर करें और पाएं {discount}% अतिरिक्त छूट। डिलीवरी 24 घंटे में। पुष्टि के लिए YES लिखें।"
    },
    "DIWALI": {
        "en": "🪔 Diwali Bumper Offer! Stock up on premium {sku_name} for gifting. Book {cartons} cartons today to unlock {discount}% festive cash discount. Fast doorstep delivery.",
        "bn": "🪔 দেওয়ালি বাম্পার অফার! উপহারের জন্য {sku_name} স্টক করুন। আজই {cartons} কার্টুন বুকিং করে {discount}% ক্যাশ ডিসকাউন্ট উপভোগ করুন। দ্রুত ডেলিভারি।",
        "hi": "🪔 दिवाली बंपर ऑफर! उपहार के लिए {sku_name} का स्टॉक करें। आज ही {cartons} कार्टन बुक करें और {discount}% का विशेष डिस्काउंट पाएं। सुरक्षित डिलीवरी।"
    },
    "REGULAR": {
        "en": "📦 Stock Replenishment Reminder: Your {sku_name} inventory is running low. Order {cartons} cartons today to avoid customer stockouts tomorrow.",
        "bn": "📦 স্টক রিমাইন্ডার: আপনার দোকানে {sku_name} প্রায় শেষ। আগামীকাল স্টকআউট এড়াতে আজই {cartons} কার্টুন অর্ডার করুন।",
        "hi": "📦 स्टॉक रिमाइंडर: आपकी दुकान में {sku_name} खत्म होने वाला है। कल माल की कमी से बचने के लिए आज ही {cartons} कार्टन ऑर्डर करें।"
    }
}


import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock client
try:
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
except Exception as e:
    logger.error(f"Failed to initialize bedrock client: {e}")
    bedrock = None

def generate_promotional_message(
    sku_name: str,
    recommended_cartons: int,
    festival_key: str = "DURGA_PUJA",
    discount_pct: float = 3.5,
    cutoff_day: str = "Wednesday"
) -> Dict[str, str]:
    """
    Produces formatted broadcast copy for retail store WhatsApp alerts using Amazon Bedrock.
    Falls back to templates if Bedrock fails.
    """
    festival_data = PROMOTION_TEMPLATES.get(festival_key.upper(), PROMOTION_TEMPLATES["REGULAR"])
    
    safe_sku_name = sku_name.replace("{", "").replace("}", "").strip() or "Biscuit"
    safe_cutoff_day = cutoff_day.replace("{", "").replace("}", "").strip() or "Friday"
    cartons = max(1, int(recommended_cartons))
    safe_discount = round(float(discount_pct), 1)

    en_msg = festival_data["en"].format(
        sku_name=safe_sku_name, cartons=cartons, discount=safe_discount, cutoff_day=safe_cutoff_day
    )
    bn_msg = festival_data["bn"].format(
        sku_name=safe_sku_name, cartons=cartons, discount=safe_discount, cutoff_day=safe_cutoff_day
    )
    hi_msg = festival_data["hi"].format(
        sku_name=safe_sku_name, cartons=cartons, discount=safe_discount, cutoff_day=safe_cutoff_day
    )

    if bedrock:
        try:
            prompt = f"Write a short, exciting SMS promotional alert for retail store owners in English. The product is {safe_sku_name}. They should order {cartons} cartons before {safe_cutoff_day} to get a {safe_discount}% discount for the {festival_key} festival. Make it max 2 sentences."
            
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-sonnet-20240229-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                })
            )
            response_body = json.loads(response.get('body').read())
            ai_en_msg = response_body.get('content')[0].get('text').strip()
            
            if ai_en_msg:
                en_msg = f"✨ [AI] {ai_en_msg}"
        except Exception as e:
            logger.error(f"Bedrock generation failed, using fallback. Error: {e}")

    return {
        "festival": festival_key,
        "sku_name": safe_sku_name,
        "cartons": cartons,
        "english": en_msg,
        "bengali": bn_msg,
        "hindi": hi_msg
    }
