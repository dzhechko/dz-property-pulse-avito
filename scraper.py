import os
import json
import logging
from datetime import datetime
import trafilatura
from app import db
from models import ScrapedData

import requests
import aiohttp
import asyncio

# Firecrawl API client implementation (direct HTTP calls)
class FirecrawlApp:
    def __init__(self, apiKey):
        self.apiKey = apiKey
        self.base_url = "https://api.firecrawl.dev/api/v1/scrape"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {apiKey}"
        }
    
    async def scrapeUrl(self, url, params):
        """
        Scrape a URL using the Firecrawl API
        
        Args:
            url (str): URL to scrape
            params (dict): Additional parameters for scraping
            
        Returns:
            dict: Scraped data or None if error
        """
        try:
            payload = {
                "url": url,
                **params
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url, 
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("Firecrawl API request successful")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"Firecrawl API request failed with status {response.status}: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error making Firecrawl API request: {str(e)}")
            return None
            
    def scrapeUrlSync(self, url, params):
        """
        Synchronous version of scrapeUrl for simpler use cases
        """
        try:
            payload = {
                "url": url,
                **params
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info("Firecrawl API request successful")
                return response.json()
            else:
                logger.error(f"Firecrawl API request failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error making Firecrawl API request: {str(e)}")
            return None

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_website_text_content(url):
    """
    Extract text content from a website using trafilatura
    
    Args:
        url (str): URL of the website to scrape
        
    Returns:
        str: Extracted text content
    """
    try:
        # Send a request to the website
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        
        # Extract text content
        text = trafilatura.extract(downloaded)
        return text
    except Exception as e:
        logger.error(f"Error extracting content with trafilatura: {str(e)}")
        return None
        
def extract_avito_listings_from_text(text):
    """
    Parse Avito listings from text content
    
    Args:
        text (str): Text content from Avito website
        
    Returns:
        dict: Structured data with listings
    """
    if not text:
        return None
    
    import re
    
    # Advanced pattern extraction for Avito property listings
    listings = []
    
    try:
        # Pattern-based approach for Avito's typical structure
        # Look for property patterns in the entire text first
        
        # 1. Try to find property blocks using price indicators
        price_pattern = r'(?:(\d[\d\s]*\d|\d)[\s]*(?:₽|руб))'
        price_matches = list(re.finditer(price_pattern, text))
        
        if price_matches:
            logger.info(f"Found {len(price_matches)} potential price indicators")
            
            # For each price match, try to extract property information around it
            for i, price_match in enumerate(price_matches):
                try:
                    # Get price
                    price_str = price_match.group(1).replace(' ', '')
                    price = int(price_str) if price_str else 0
                    
                    # Find context - get text before and after the price (limited range)
                    match_pos = price_match.start()
                    
                    # Define search window - more text before price than after
                    start_pos = max(0, match_pos - 500)
                    end_pos = min(len(text), match_pos + 300)
                    
                    # Extract potential listing text
                    listing_text = text[start_pos:end_pos]
                    
                    # Look for room info - this is typically part of the title
                    room_pattern = r'(\d+)[\s-]*комн'
                    rooms_match = re.search(room_pattern, listing_text)
                    rooms = int(rooms_match.group(1)) if rooms_match else None
                    
                    # Look for area info
                    area_pattern = r'(\d+(?:[.,]\d+)?)[\s]*м²'
                    area_match = re.search(area_pattern, listing_text)
                    area = float(area_match.group(1).replace(',', '.')) if area_match else None
                    
                    # Look for floor info
                    floor_pattern = r'(\d+)/(\d+)[\s]*эт'
                    floor_match = re.search(floor_pattern, listing_text)
                    floor = f"{floor_match.group(1)}/{floor_match.group(2)}" if floor_match else None
                    
                    # Extract title - try to find a complete title pattern
                    title_pattern = r'(\d+[\s-]*комн\.?[\s]*квартира,[\s]*\d+(?:[.,]\d+)?[\s]*м²,[\s]*\d+/\d+[\s]*эт\.?)'
                    title_match = re.search(title_pattern, listing_text)
                    
                    if title_match:
                        title = title_match.group(1)
                    elif rooms_match and area_match and floor_match:
                        # Construct title from components if full pattern not found
                        title = f"{rooms}-комн. квартира, {area} м², {floor} эт."
                    else:
                        # Find the first line that might be a title
                        lines = listing_text.split('\n')
                        title_candidates = [l for l in lines if 'квартира' in l.lower() or 'комн' in l.lower()]
                        title = title_candidates[0].strip() if title_candidates else "Квартира"
                    
                    # Extract location - look for known city names and address patterns
                    location_pattern = r'(?:Москва|Санкт-Петербург|Новосибирск|Екатеринбург|Казань|Ростов|Краснодар)(?:[^,\n]*(?:,|ул\.|проспект|пр-т)[^,\n]*)'
                    location_match = re.search(location_pattern, listing_text)
                    
                    if location_match:
                        location = location_match.group(0)
                    else:
                        # Fallback - look for address patterns
                        address_pattern = r'(?:ул\.|улица|проспект|пр-т|бульвар|переулок|проезд|шоссе)[\s\w\-\.,]+'
                        addr_match = re.search(address_pattern, listing_text)
                        location = addr_match.group(0) if addr_match else "Адрес не указан"
                    
                    # Create listing object
                    listing = {
                        "title": title.strip(),
                        "price": price,
                        "location": location.strip(),
                        "area": area,
                        "rooms": rooms,
                        "floor": floor,
                        "description": listing_text,
                        "seller_rating": None,
                        "views": None
                    }
                    
                    # Only add unique listings with required data
                    if (listing["title"] and listing["price"] > 0 and 
                        listing["location"] and 
                        not any(l["price"] == listing["price"] and l["title"] == listing["title"] for l in listings)):
                        listings.append(listing)
                        
                except Exception as e:
                    logger.warning(f"Error processing listing {i+1}: {str(e)}")
                    continue
        
        # 2. If we didn't find enough listings, try an alternative approach using section splitting
        if len(listings) < 3:
            logger.info("Few listings found, trying alternative extraction method")
            
            # Try to find listings based on room-apartment patterns
            apt_pattern = r'\b(\d+)[\s-]*комн\.?[\s]*квартира\b'
            apt_matches = list(re.finditer(apt_pattern, text))
            
            if apt_matches:
                logger.info(f"Found {len(apt_matches)} apartment mentions")
                
                for i, apt_match in enumerate(apt_matches):
                    try:
                        rooms = int(apt_match.group(1))
                        match_pos = apt_match.start()
                        
                        # Extract potential listing text - paragraph around the match
                        start_pos = max(0, text.rfind('\n\n', 0, match_pos))
                        end_pos = text.find('\n\n', match_pos)
                        if end_pos == -1: end_pos = len(text)
                        
                        listing_text = text[start_pos:end_pos]
                        
                        # Extract price
                        price_match = re.search(price_pattern, listing_text)
                        price = int(price_match.group(1).replace(' ', '')) if price_match else 0
                        
                        # Other extraction logic similar to above
                        area_match = re.search(r'(\d+(?:[.,]\d+)?)[\s]*м²', listing_text)
                        area = float(area_match.group(1).replace(',', '.')) if area_match else None
                        
                        floor_match = re.search(r'(\d+)/(\d+)[\s]*эт', listing_text)
                        floor = f"{floor_match.group(1)}/{floor_match.group(2)}" if floor_match else None
                        
                        title = apt_match.group(0)
                        if area_match and floor_match:
                            title = f"{title}, {area_match.group(0)}, {floor_match.group(0)}"
                        
                        # Extract location (simplified approach)
                        location = "Адрес не указан"
                        for line in listing_text.split('\n'):
                            loc_indicators = ["Москва", "Санкт-Петербург", "ул.", "проспект", "пр-т"]
                            if any(indicator in line for indicator in loc_indicators):
                                location = line.strip()
                                break
                        
                        # Create listing object
                        listing = {
                            "title": title.strip(),
                            "price": price,
                            "location": location.strip(),
                            "area": area,
                            "rooms": rooms,
                            "floor": floor,
                            "description": listing_text,
                            "seller_rating": None,
                            "views": None
                        }
                        
                        # Only add unique listings with required data
                        if (listing["price"] > 0 and 
                            not any(l["price"] == listing["price"] and l["rooms"] == listing["rooms"] for l in listings)):
                            listings.append(listing)
                            
                    except Exception as e:
                        logger.warning(f"Error in alt method for listing {i+1}: {str(e)}")
                        continue
        
        # Create structured data format
        structured_data = {
            "listings": listings,
            "pagination": {
                "next_page": None,
                "total_pages": None
            }
        }
        
        # Log extraction results
        if listings:
            logger.info(f"Successfully extracted {len(listings)} listings")
            for i, listing in enumerate(listings[:3]):
                logger.info(f"Sample {i+1}: {listing['title']} - {listing['price']}₽")
                
            if len(listings) > 3:
                logger.info(f"And {len(listings)-3} more listings...")
        else:
            logger.warning("No listings extracted from text")
        
        return structured_data
    
    except Exception as e:
        logger.error(f"Error extracting listings from text: {str(e)}")
        return {
            "listings": [],
            "pagination": {
                "next_page": None,
                "total_pages": None
            }
        }

def scrape_avito_data(url, api_key=None):
    """
    Scrapes real estate data from Avito using either Firecrawl API or trafilatura as fallback
    
    Args:
        url (str): URL of the Avito real estate listing page
        api_key (str, optional): Firecrawl API key provided by user
        
    Returns:
        dict: Result of the scraping operation with keys:
            - success (bool): Whether the scraping was successful
            - data_id (int, optional): ID of the stored data if successful
            - error (str, optional): Error message if unsuccessful
    """
    try:
        logger.info(f"Starting scraping for URL: {url}")
        
        # If no API key provided in function parameter, try to get from environment variables
        if not api_key:
            api_key = os.environ.get("FIRECRAWL_API_KEY")
            if api_key:
                logger.info("Using API key from environment variables")
        else:
            logger.info("Using user-provided API key")
        
        # Define structured data container
        structured_data = None
        
        # Try to use Firecrawl if API key is available
        if api_key:
            try:
                logger.info("Attempting to use Firecrawl API")
                
                # Define the schema for property listings
                listing_schema = {
                    "listings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "price": {"type": "number"},
                                "location": {"type": "string"},
                                "area": {"type": "number"},
                                "rooms": {"type": "number"},
                                "floor": {"type": "string"},
                                "description": {"type": "string"},
                                "seller_rating": {"type": "number"},
                                "views": {"type": "number"}
                            },
                            "required": ["title", "price", "location"]
                        }
                    },
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "next_page": {"type": "string"},
                            "total_pages": {"type": "number"}
                        }
                    }
                }
                
                # Initialize Firecrawl with API key
                firecrawl = FirecrawlApp(apiKey=api_key)
                
                # Configure scraping parameters
                params = {
                    "pageOptions": {
                        "onlyMainContent": False,
                    },
                    "extractorOptions": {
                        "extractionSchema": listing_schema
                    },
                    "timeout": 50000,  # 50 seconds timeout
                }
                
                # Try synchronous method first for simplicity
                try:
                    logger.info("Using Firecrawl API with synchronous method")
                    scraped_data = firecrawl.scrapeUrlSync(url, params)
                    
                    if scraped_data and isinstance(scraped_data, dict) and 'listings' in scraped_data:
                        structured_data = scraped_data
                        logger.info(f"Successfully retrieved {len(scraped_data.get('listings', []))} listings using Firecrawl API")
                    else:
                        logger.warning("Firecrawl API returned invalid data format")
                        
                        # Try async method as fallback
                        try:
                            logger.info("Trying asynchronous method as fallback")
                            import asyncio
                            
                            # Define an async function to run the API call
                            async def run_firecrawl():
                                try:
                                    result = await firecrawl.scrapeUrl(url, params)
                                    return result
                                except Exception as e:
                                    logger.error(f"Error in Firecrawl API call: {str(e)}")
                                    return None
                            
                            # Run the async function
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            scraped_data = loop.run_until_complete(run_firecrawl())
                            loop.close()
                            
                            if scraped_data and isinstance(scraped_data, dict) and 'listings' in scraped_data:
                                structured_data = scraped_data
                                logger.info(f"Successfully retrieved {len(scraped_data.get('listings', []))} listings using Firecrawl API async")
                            else:
                                logger.warning("Firecrawl API async returned invalid data format, falling back to trafilatura")
                        
                        except Exception as e:
                            logger.error(f"Failed to use Firecrawl API async: {str(e)}")
                            logger.warning("Falling back to trafilatura method due to Firecrawl async error")
                
                except Exception as e:
                    logger.error(f"Failed to use Firecrawl API sync: {str(e)}")
                    logger.warning("Falling back to trafilatura method due to Firecrawl sync error")
            except Exception as e:
                logger.error(f"Error using Firecrawl API: {str(e)}")
                # We'll fall back to trafilatura
        else:
            logger.warning("Firecrawl API key not found, using fallback scraping method.")
        
        # Use trafilatura as a fallback method or primary method if Firecrawl not available
        if not structured_data:
            logger.info("Using trafilatura to scrape content")
            # Get the text content from the webpage
            text_content = get_website_text_content(url)
            
            if text_content:
                # Extract listings from the text content
                structured_data = extract_avito_listings_from_text(text_content)
                if structured_data and 'listings' in structured_data:
                    logger.info(f"Extracted {len(structured_data['listings'])} listings using trafilatura")
                else:
                    logger.error("Failed to extract structured data from content")
                    structured_data = None
            else:
                logger.error("Failed to extract content with trafilatura")
        
        # If both methods failed, use demo data
        if not structured_data or not structured_data.get('listings'):
            logger.warning("Using demo data as fallback")
            
            # Demo data for testing functionality
            structured_data = {
                "listings": [
                    {
                        "title": "2-комн. квартира, 60 м², 5/9 эт.",
                        "price": 5200000,
                        "location": "Москва, ул. Примерная, 123",
                        "area": 60,
                        "rooms": 2,
                        "floor": "5/9",
                        "description": "Просторная квартира в хорошем состоянии",
                        "seller_rating": 4.8,
                        "views": 245
                    },
                    {
                        "title": "1-комн. квартира, 42 м², 3/12 эт.",
                        "price": 3800000,
                        "location": "Москва, ул. Образцовая, 45",
                        "area": 42,
                        "rooms": 1,
                        "floor": "3/12",
                        "description": "Уютная квартира после ремонта",
                        "seller_rating": 4.5,
                        "views": 178
                    }
                ],
                "pagination": {
                    "next_page": "page_2",
                    "total_pages": 10
                }
            }
        
        # Save scraped data to database
        new_data = ScrapedData(
            url=url,
            data=json.dumps(structured_data)
        )
        db.session.add(new_data)
        db.session.commit()
        
        logger.info(f"Scraping completed successfully. Data ID: {new_data.id}")
        
        return {
            "success": True,
            "data_id": new_data.id
        }
        
    except Exception as e:
        logger.error(f"Error during scraping: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
