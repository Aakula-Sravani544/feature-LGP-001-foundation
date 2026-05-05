"""
Day 9 — Additional AI Features
LeadPulse Pro AI Engine
Features:
- Lead scoring (0-100)
- Qualification summary
- Outreach message generation
- Industry classification
- Batch processing (10 leads per API call)
- Day 9: Sub-region generation, Email guessing, Sentiment, Trends, Contact finder
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
# FEATURE 1 — Sub-Region Generator
# ==========================================
def generate_sub_regions(city: str) -> list:
    """
    Use Gemini to decompose a city into 10-20 named districts.
    Enables parallel searches per district for more coverage.

    Args:
        city: City name e.g. 'Hyderabad'

    Returns:
        List of district/sub-region names
    """
    model = setup_gemini()

    if model:
        try:
            prompt = f"""List the 10 most important business districts and neighborhoods in {city}, India.
Return ONLY a JSON array of strings. No other text. No markdown.
Example: ["Banjara Hills", "Jubilee Hills", "Hitech City"]"""

            response = model.generate_content(prompt)
            raw = response.text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            regions = json.loads(raw)
            if isinstance(regions, list):
                logger.info(f"Generated {len(regions)} sub-regions for {city}")
                return regions[:15]
        except Exception as e:
            logger.error(f"Sub-region generation failed: {e}")

    # Fallback — hardcoded major Indian cities
    fallback_regions = {
        "hyderabad": ["Banjara Hills", "Jubilee Hills", "Hitech City",
                     "Gachibowli", "Secunderabad", "Kukatpally",
                     "Ameerpet", "Madhapur", "Kondapur", "Begumpet"],
        "chennai": ["T Nagar", "Anna Nagar", "Adyar", "Velachery",
                   "Nungambakkam", "Mylapore", "Tambaram", "OMR",
                   "Porur", "Chromepet"],
        "bangalore": ["Koramangala", "Indiranagar", "Whitefield",
                     "Electronic City", "Jayanagar", "HSR Layout",
                     "Marathahalli", "JP Nagar", "Bannerghatta", "BTM"],
        "mumbai": ["Andheri", "Bandra", "Powai", "Worli",
                  "Malad", "Goregaon", "Juhu", "Kurla",
                  "Thane", "Navi Mumbai"],
        "delhi": ["Connaught Place", "Lajpat Nagar", "Dwarka",
                 "Rohini", "Karol Bagh", "Saket", "Noida",
                 "Gurgaon", "Janakpuri", "Pitampura"]
    }
    city_lower = city.lower()
    for key in fallback_regions:
        if key in city_lower:
            return fallback_regions[key]
    return [city]


# ==========================================
# FEATURE 2 — Email Pattern Guesser
# ==========================================
def guess_email_pattern(
    business_name: str,
    website: str
) -> str:
    """
    Guess likely business email from name and domain.

    Args:
        business_name: Business name
        website: Website URL

    Returns:
        Guessed email string or empty string
    """
    if not website:
        return ""

    try:
        # Extract domain from website
        domain = website.replace("https://", "").replace("http://", "")
        domain = domain.replace("www.", "").split("/")[0].strip()

        if not domain:
            return ""

        # Common email patterns
        patterns = [
            f"info@{domain}",
            f"contact@{domain}",
            f"hello@{domain}",
            f"sales@{domain}",
            f"enquiry@{domain}",
        ]

        # Use AI to pick best pattern if available
        model = setup_gemini()
        if model:
            try:
                prompt = f"""Given business name '{business_name}' and domain '{domain}',
what is the most likely professional email address?
Return ONLY the email address. No other text."""
                response = model.generate_content(prompt)
                guessed = response.text.strip()
                if "@" in guessed and domain in guessed:
                    return guessed
            except:
                pass

        return patterns[0]

    except Exception as e:
        logger.debug(f"Email pattern guess failed: {e}")
        return ""


# ==========================================
# FEATURE 3 — Sentiment Analyser
# ==========================================
def analyze_sentiment(lead: Dict) -> str:
    """
    Analyse business sentiment from rating and review count.

    Args:
        lead: Lead dictionary with rating and reviews

    Returns:
        Sentiment label: Positive/Neutral/Negative
    """
    try:
        rating = float(lead.get("rating", 0))
        reviews_str = str(lead.get("reviews", "0")).replace(",", "").strip()
        reviews = int(reviews_str) if reviews_str.isdigit() else 0
    except:
        return "Neutral"

    model = setup_gemini()

    if model and rating > 0:
        try:
            prompt = f"""Business: {lead.get('name', '')}
Rating: {rating}/5
Reviews: {reviews}
Category: {lead.get('category', '')}

Analyze customer sentiment in one word: Positive, Neutral, or Negative.
Return ONLY one word."""
            response = model.generate_content(prompt)
            sentiment = response.text.strip()
            if sentiment in ["Positive", "Neutral", "Negative"]:
                return sentiment
        except:
            pass

    # Rule-based fallback
    if rating >= 4.3:
        return "Positive"
    elif rating >= 3.5:
        return "Neutral"
    else:
        return "Negative"


# ==========================================
# FEATURE 4 — Trend Predictor
# ==========================================
def predict_trend(lead: Dict) -> str:
    """
    Predict if business is growing or declining based on signals.

    Args:
        lead: Lead dictionary

    Returns:
        Trend label: Growing/Stable/Declining
    """
    try:
        rating = float(lead.get("rating", 0))
        reviews_str = str(lead.get("reviews", "0")).replace(",", "").strip()
        reviews = int(reviews_str) if reviews_str.isdigit() else 0
    except:
        return "Stable"

    model = setup_gemini()

    if model and rating > 0:
        try:
            prompt = f"""Business: {lead.get('name', '')}
Rating: {rating}/5
Total Reviews: {reviews}
Has Website: {'Yes' if lead.get('website') else 'No'}
Has Social Media: {'Yes' if lead.get('social_media') else 'No'}

Based on these signals, is this business Growing, Stable, or Declining?
Return ONLY one word: Growing, Stable, or Declining."""
            response = model.generate_content(prompt)
            trend = response.text.strip()
            if trend in ["Growing", "Stable", "Declining"]:
                return trend
        except:
            pass

    # Rule-based fallback
    if rating >= 4.5 and reviews >= 1000:
        return "Growing"
    elif rating >= 4.0 and reviews >= 100:
        return "Stable"
    else:
        return "Declining"


# ==========================================
# FEATURE 5 — Contact Finder AI
# ==========================================
def find_contact_person(lead: Dict) -> str:
    """
    Suggest likely decision-maker name and title for a business.

    Args:
        lead: Lead dictionary

    Returns:
        Suggested contact string e.g. "Marketing Manager"
    """
    model = setup_gemini()

    if model:
        try:
            prompt = f"""For a {lead.get('category', 'business')} called '{lead.get('name', '')}',
what job title would be the best decision-maker to contact for B2B sales?
Return ONLY the job title. Max 5 words. No other text."""
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            pass

    # Rule-based fallback by category
    category = lead.get("category", "").lower()
    if "restaurant" in category or "hotel" in category:
        return "General Manager"
    elif "it" in category or "tech" in category or "software" in category:
        return "CEO / Founder"
    elif "hospital" in category or "clinic" in category:
        return "Practice Manager"
    elif "school" in category or "college" in category:
        return "Principal / Director"
    else:
        return "Business Owner"


# ==========================================
# MAIN AI ENRICHMENT FUNCTION
# ==========================================
def enrich_leads_with_ai(leads: List[Dict]) -> List[Dict]:
    """
    Enrich all leads with full AI analysis including Day 9 features.
    Processes in batches of 10. Falls back to rule-based if no API key.

    Args:
        leads: List of lead dicts

    Returns:
        Enriched leads with all AI fields populated
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

        # Core AI analysis (score, qualification, outreach, industry)
        if model:
            analyses = analyze_leads_batch(model, batch)
        else:
            analyses = [rule_based_score(l) for l in batch]

        for lead, analysis in zip(batch, analyses):
            try:
                # Store core analysis
                lead["ai_analysis"] = json.dumps(analysis)
                lead["ai_score"] = analysis.get("score", 0)

                # Day 9 Feature 2: Email Pattern Guesser
                if not lead.get("email") and lead.get("website"):
                    guessed = guess_email_pattern(
                        lead.get("name", ""),
                        lead.get("website", "")
                    )
                    if guessed:
                        lead["email"] = guessed

                # Day 9 Feature 3: Sentiment
                sentiment = analyze_sentiment(lead)

                # Day 9 Feature 4: Trend
                trend = predict_trend(lead)

                # Day 9 Feature 5: Contact finder
                contact = find_contact_person(lead)

                # Store Day 9 results in additional_data
                existing = []
                try:
                    additional_raw = lead.get("additional_data", "[]")
                    existing = json.loads(additional_raw) if additional_raw else []
                    if not isinstance(existing, list):
                        existing = []
                except:
                    existing = []

                day9_data = {
                    "sentiment": sentiment,
                    "trend": trend,
                    "suggested_contact": contact,
                    "tech_stack": existing
                }
                lead["additional_data"] = json.dumps(day9_data)

                # Store sub_region — extract neighbourhood from address
                if not lead.get("sub_region"):
                    address = lead.get("address", "")
                    sub_region = ""
                    if address and "," in address:
                        parts = [p.strip() for p in address.split(",")]
                        # Filter out state names, country, pincodes
                        skip_words = [
                            "india", "telangana", "karnataka", "maharashtra",
                            "tamil nadu", "andhra pradesh", "kerala", "gujarat",
                            "rajasthan", "punjab", "haryana", "uttar pradesh",
                            "west bengal", "madhya pradesh", "bihar", "odisha"
                        ]
                        for part in parts:
                            part_clean = part.strip()
                            # Skip if it's a pincode (all digits)
                            if part_clean.isdigit():
                                continue
                            # Skip if it contains digits (pincode mixed with state)
                            if any(char.isdigit() for char in part_clean):
                                continue
                            # Skip if it's a state or country name
                            if part_clean.lower() in skip_words:
                                continue
                            # Skip if too short
                            if len(part_clean) < 4:
                                continue
                            # Skip if it's the full city name
                            if part_clean.lower() in ["hyderabad", "chennai", "bangalore",
                                "bengaluru", "mumbai", "delhi", "kolkata", "pune",
                                "ahmedabad", "jaipur", "vijayawada", "visakhapatnam"]:
                                continue
                            # This is likely a neighbourhood/district
                            sub_region = part_clean
                            break
                    lead["sub_region"] = sub_region

            except Exception as e:
                logger.error(f"Day 9 enrichment failed for {lead.get('name')}: {e}")

        if model and i + BATCH_SIZE < total:
            time.sleep(1)

    logger.info(f"Day 9 AI enrichment complete for {total} leads")
    return leads


# ==========================================
# SINGLE LEAD AI ANALYSIS
# ==========================================
def analyze_single_lead(lead: Dict, use_ai: bool = True) -> Dict:
    """
    Analyze a single lead with AI or rule-based fallback.
    Includes Day 9 features: Sentiment, Trend, Contact, Email Guessing.

    Args:
        lead: Single lead dictionary
        use_ai: If False, forces rule-based scoring even if API key exists.

    Returns:
        Lead with ai_analysis and additional_data populated
    """
    model = setup_gemini() if use_ai else None

    # Core Analysis
    if model:
        analyses = analyze_leads_batch(model, [lead])
        if analyses:
            analysis = analyses[0]
            lead["ai_analysis"] = json.dumps(analysis)
            lead["ai_score"] = analysis.get("score", 0)
    else:
        analysis = rule_based_score(lead)
        lead["ai_analysis"] = json.dumps(analysis)
        lead["ai_score"] = analysis.get("score", 0)

    # Day 9 Features
    try:
        # Email Pattern Guesser
        if not lead.get("email") and lead.get("website"):
            guessed = guess_email_pattern(lead.get("name", ""), lead.get("website", ""))
            if guessed:
                lead["email"] = guessed

        # Sentiment, Trend, Contact
        sentiment = analyze_sentiment(lead)
        trend = predict_trend(lead)
        contact = find_contact_person(lead)

        # Tech stack preservation
        existing_tech = []
        try:
            raw_add = lead.get("additional_data", "")
            if raw_add:
                parsed = json.loads(raw_add)
                existing_tech = parsed if isinstance(parsed, list) else []
        except:
            pass

        day9_data = {
            "sentiment": sentiment,
            "trend": trend,
            "suggested_contact": contact,
            "tech_stack": existing_tech
        }
        lead["additional_data"] = json.dumps(day9_data)

        # Store sub_region — extract neighbourhood from address
        if not lead.get("sub_region"):
            address = lead.get("address", "")
            sub_region = ""
            if address and "," in address:
                parts = [p.strip() for p in address.split(",")]
                # Filter out state names, country, pincodes
                skip_words = [
                    "india", "telangana", "karnataka", "maharashtra",
                    "tamil nadu", "andhra pradesh", "kerala", "gujarat",
                    "rajasthan", "punjab", "haryana", "uttar pradesh",
                    "west bengal", "madhya pradesh", "bihar", "odisha"
                ]
                for part in parts:
                    part_clean = part.strip()
                    # Skip if it's a pincode (all digits)
                    if part_clean.isdigit():
                        continue
                    # Skip if it contains digits (pincode mixed with state)
                    if any(char.isdigit() for char in part_clean):
                        continue
                    # Skip if it's a state or country name
                    if part_clean.lower() in skip_words:
                        continue
                    # Skip if too short
                    if len(part_clean) < 4:
                        continue
                    # Skip if it's the full city name
                    if part_clean.lower() in ["hyderabad", "chennai", "bangalore",
                        "bengaluru", "mumbai", "delhi", "kolkata", "pune",
                        "ahmedabad", "jaipur", "vijayawada", "visakhapatnam"]:
                        continue
                    # This is likely a neighbourhood/district
                    sub_region = part_clean
                    break
            lead["sub_region"] = sub_region

    except Exception as e:
        logger.error(f"Single lead enrichment failed: {e}")

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

__all__ = [
    'enrich_leads_with_ai',
    'analyze_single_lead',
    'get_ai_score',
    'generate_sub_regions',
    'guess_email_pattern',
    'analyze_sentiment',
    'predict_trend',
    'find_contact_person',
    'rule_based_score'
]
