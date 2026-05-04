"""
Day 8 — Gemini AI Integration
LeadPulse Pro AI Engine
Features:
- Lead scoring (0-100)
- Qualification summary
- Outreach message generation
- Industry classification
- Batch processing (10 leads per API call)
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional

import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BATCH_SIZE = 10
MAX_RETRIES = 3
RETRY_DELAY = 2

# ==========================================
# GEMINI CLIENT SETUP
# ==========================================
def setup_gemini() -> Optional[Any]:
    """
    Initialize Gemini AI client.

    Returns:
        Configured Gemini model or None if no API key
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not found — AI features disabled")
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        logger.info("Gemini AI client initialized successfully")
        return model
    except Exception as e:
        logger.error(f"Gemini setup failed: {e}")
        return None


# ==========================================
# AI PROMPT TEMPLATE (from PDF Section 5.2)
# ==========================================
def build_prompt(leads: List[Dict]) -> str:
    """
    Build structured AI prompt for batch lead analysis.
    Follows the standard prompt template from LeadPulse Pro docs.

    Args:
        leads: List of lead dicts to analyze

    Returns:
        Formatted prompt string
    """
    leads_text = ""
    for i, lead in enumerate(leads):
        leads_text += f"""
Lead {i+1}:
- Name: {lead.get('name', '')}
- Category: {lead.get('category', '')}
- Rating: {lead.get('rating', '0')}/5
- Reviews: {lead.get('reviews', '0')}
- Address: {lead.get('address', '')}
- Website: {lead.get('website', '')}
- Phone: {lead.get('phone', '')}
- Email: {lead.get('email', '')}
- Description: {lead.get('description', '')[:200]}
"""

    prompt = f"""You are a B2B lead qualification expert. Analyze these business leads and respond with valid JSON only. No preamble. No markdown. No backticks.

Leads to analyze:
{leads_text}

Respond with a JSON array containing exactly {len(leads)} objects, one per lead, in this exact schema:
[
  {{
    "score": <integer 0-100 based on rating, reviews, website quality, contact completeness>,
    "qualification": "<3 sentence explanation of why this lead is worth pursuing>",
    "suggested_email": "<guessed professional email if not provided, else use existing>",
    "outreach_draft": "<personalized cold email draft under 100 words>",
    "industry": "<business vertical: Restaurant/Hotel/IT/Healthcare/Retail/Education/Finance/Other>"
  }}
]

Scoring criteria:
- Rating 4.5+ = +30 points
- Rating 4.0-4.4 = +20 points
- Rating below 4.0 = +10 points
- Reviews 1000+ = +20 points
- Reviews 100-999 = +10 points
- Has website = +15 points
- Has email = +15 points
- Has phone = +10 points
- Complete address = +10 points

Important: Return ONLY the JSON array. No other text."""

    return prompt


# ==========================================
# RULE-BASED FALLBACK SCORING
# ==========================================
def rule_based_score(lead: Dict) -> Dict:
    """
    Calculate lead score without AI using rule-based logic.
    Used when no GEMINI_API_KEY is provided.

    Args:
        lead: Lead dictionary

    Returns:
        AI analysis dict with score and basic fields
    """
    score = 0

    # Rating score
    try:
        rating = float(lead.get("rating", 0))
        if rating >= 4.5:
            score += 30
        elif rating >= 4.0:
            score += 20
        elif rating > 0:
            score += 10
    except:
        pass

    # Reviews score
    try:
        reviews_str = str(lead.get("reviews", "0")).replace(",", "").strip()
        reviews = int(reviews_str) if reviews_str.isdigit() else 0
        if reviews >= 1000:
            score += 20
        elif reviews >= 100:
            score += 10
    except:
        pass

    # Contact completeness
    if lead.get("website"):
        score += 15
    if lead.get("email"):
        score += 15
    if lead.get("phone"):
        score += 10
    if lead.get("address"):
        score += 10

    name = lead.get("name", "")
    category = lead.get("category", "Other")

    return {
        "score": min(score, 100),
        "qualification": f"{name} is a {category} business with a score of {score}/100 based on available data.",
        "suggested_email": lead.get("email", ""),
        "outreach_draft": f"Hi, I came across {name} and would love to connect about potential opportunities. Would you be open to a quick call?",
        "industry": category
    }


# ==========================================
# BATCH AI PROCESSING
# ==========================================
def analyze_leads_batch(
    model: Any,
    leads: List[Dict]
) -> List[Dict]:
    """
    Analyze a batch of leads using Gemini AI.
    Processes 10 leads per API call as per Day 8 spec.

    Args:
        model: Configured Gemini model
        leads: List of leads to analyze

    Returns:
        List of AI analysis dicts
    """
    prompt = build_prompt(leads)

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()

            # Clean response — remove markdown if present
            raw = raw.replace("```json", "").replace("```", "").strip()

            # Parse JSON
            analyses = json.loads(raw)

            if isinstance(analyses, list) and len(analyses) == len(leads):
                logger.info(f"Batch of {len(leads)} leads analyzed successfully")
                return analyses
            else:
                logger.warning(f"Response length mismatch. Expected {len(leads)}, got {len(analyses)}")
                return [rule_based_score(l) for l in leads]

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Gemini API error attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    logger.warning("All retries failed — using rule-based fallback")
    return [rule_based_score(l) for l in leads]


# ==========================================
# MAIN AI ENRICHMENT FUNCTION
# ==========================================
def enrich_leads_with_ai(leads: List[Dict]) -> List[Dict]:
    """
    Main function to enrich all leads with AI analysis.
    Processes in batches of 10 as per Day 8 spec.
    Falls back to rule-based scoring if no API key.

    Args:
        leads: List of lead dicts

    Returns:
        Leads with ai_analysis field populated
    """
    if not leads:
        return leads

    model = setup_gemini()

    total = len(leads)
    logger.info(f"Starting AI enrichment for {total} leads")

    for i in range(0, total, BATCH_SIZE):
        batch = leads[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        logger.info(f"Processing batch {batch_num} ({len(batch)} leads)")

        if model:
            analyses = analyze_leads_batch(model, batch)
        else:
            logger.info("No API key — using rule-based scoring")
            analyses = [rule_based_score(l) for l in batch]

        # Store AI analysis in each lead
        for lead, analysis in zip(batch, analyses):
            try:
                lead["ai_analysis"] = json.dumps(analysis)
                # Ensure score is also available for sorting
                lead["ai_score"] = analysis.get("score", 0)
            except Exception as e:
                logger.error(f"Failed to store analysis for {lead.get('name')}: {e}")
                lead["ai_analysis"] = json.dumps(rule_based_score(lead))

        # Respect Gemini free tier rate limit
        # 60 requests/minute — wait between batches
        if model and i + BATCH_SIZE < total:
            time.sleep(1)

    logger.info(f"AI enrichment complete for {total} leads")
    return leads


# ==========================================
# SINGLE LEAD AI ANALYSIS
# ==========================================
def analyze_single_lead(lead: Dict) -> Dict:
    """
    Analyze a single lead with AI or rule-based fallback.

    Args:
        lead: Single lead dictionary

    Returns:
        Lead with ai_analysis populated
    """
    model = setup_gemini()

    if model:
        analyses = analyze_leads_batch(model, [lead])
        if analyses:
            lead["ai_analysis"] = json.dumps(analyses[0])
    else:
        lead["ai_analysis"] = json.dumps(rule_based_score(lead))

    return lead


# ==========================================
# GET AI SCORE FROM LEAD
# ==========================================
def get_ai_score(lead: Dict) -> int:
    """
    Extract AI score from lead's ai_analysis field.

    Args:
        lead: Lead dictionary with ai_analysis field

    Returns:
        Score integer 0-100
    """
    try:
        analysis = json.loads(lead.get("ai_analysis", "{}"))
        return int(analysis.get("score", 0))
    except:
        return 0
