import os
import json
import logging
import pandas as pd
import re
import io
import base64
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from app import db
from models import ScrapedData, AnalysisResult

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import E2B Code Interpreter if possible
try:
    from e2b.code_interpreter import Sandbox
except ImportError:
    # Mock the class for development if not available
    class Sandbox:
        async def runCode(self, code, options=None):
            # This is a mock method - in production, this should use the actual API
            raise NotImplementedError("E2B Code Interpreter is not available")

def get_analysis_parameters():
    """
    Returns available analysis parameters
    
    Returns:
        list: List of available analysis parameters as dictionaries
    """
    return [
        {
            'id': 'price',
            'name': 'Price Distribution',
            'description': 'Analyze distribution of property prices',
            'default_bins': 50
        },
        {
            'id': 'area',
            'name': 'Area Distribution',
            'description': 'Analyze distribution of property sizes',
            'default_bins': 30
        },
        {
            'id': 'rooms',
            'name': 'Room Count Distribution',
            'description': 'Analyze distribution of room counts',
            'default_bins': 10
        },
        {
            'id': 'seller_rating',
            'name': 'Seller Rating Distribution',
            'description': 'Analyze distribution of seller ratings',
            'default_bins': 20
        },
        {
            'id': 'views',
            'name': 'View Count Distribution',
            'description': 'Analyze distribution of listing view counts',
            'default_bins': 30
        }
    ]

def extract_number(x):
    """
    Extracts a numeric value from a string
    
    Args:
        x: Value to extract number from
        
    Returns:
        float: Extracted number or None if no number found
    """
    if pd.isna(x):
        return None
    
    # Если уже числовое значение, просто вернуть его
    if isinstance(x, (int, float)):
        return float(x)
    
    # Преобразуем в строку для поиска
    x_str = str(x)
    
    # Специальная обработка для площади из строк типа "60 м²"
    area_match = re.search(r'(\d+(?:[,.]\d+)?)(?:\s*м²|\s*кв\.м|\s*m²)', x_str)
    if area_match:
        return float(area_match.group(1).replace(',', '.'))
    
    # Общий поиск числовых значений
    matches = re.findall(r'\d+(?:[,.]\d+)?', x_str)
    return float(matches[0].replace(',', '.')) if matches else None

def remove_outliers(data):
    """
    Removes outliers from data using IQR method
    
    Args:
        data (pandas.Series): Data to remove outliers from
        
    Returns:
        pandas.Series: Data with outliers removed
    """
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    return data[(data >= lower_bound) & (data <= upper_bound)]

def format_axis_label(x, include_rub=False):
    """
    Formats axis labels for better readability
    
    Args:
        x (float): Value to format
        include_rub (bool): Whether to include ₽ symbol
        
    Returns:
        str: Formatted value
    """
    if x >= 1000000:
        return f"{x/1000000:.1f}M{'₽' if include_rub else ''}"
    elif x >= 1000:
        return f"{x/1000:.0f}K{'₽' if include_rub else ''}"
    return f"{x:.0f}{'₽' if include_rub else ''}"

def generate_visualization(data, parameter, title=None, bins=30):
    """
    Generates visualization for the given data and parameters
    
    Args:
        data (pandas.Series): Data to visualize
        parameter (str): Parameter being analyzed
        title (str, optional): Custom title for visualization
        bins (int, optional): Number of bins for histogram
        
    Returns:
        dict: Visualization data with keys:
            - image_base64 (str): Base64-encoded image data
            - statistics (dict): Statistical information
    """
    # Remove outliers
    clean_data = remove_outliers(data)
    
    # Calculate statistics
    stats = {
        'count': len(clean_data),
        'mean': float(clean_data.mean()),
        'median': float(clean_data.median()),
        'min': float(clean_data.min()),
        'max': float(clean_data.max()),
        'std': float(clean_data.std())
    }
    
    # Check data variance to determine appropriate bin strategy
    data_range = stats['max'] - stats['min']
    unique_values = clean_data.nunique()
    
    # If we have few unique values, use those values as bins
    if unique_values <= 10:
        actual_bins = sorted(clean_data.unique())
        logger.info(f"Using {len(actual_bins)} unique values as bins")
    elif unique_values < bins:
        # If we have fewer unique values than requested bins, reduce bin count
        actual_bins = min(unique_values, bins)
        logger.info(f"Adjusted bins from {bins} to {actual_bins} based on unique values")
    else:
        # Calculate bin width to avoid having empty bins
        bin_width = data_range / bins
        if bin_width < 1 and parameter in ['rooms', 'floor']:
            # For discrete data like rooms, adjust bins
            actual_bins = unique_values
            logger.info(f"Using {unique_values} bins for discrete parameter {parameter}")
        else:
            actual_bins = bins
            logger.info(f"Using {bins} bins for parameter {parameter}")
    
    # Create histogram visualization
    plt.figure(figsize=(12, 6), facecolor='white')
    # Add a small amount of random noise to improve histogram display 
    # for parameters with few unique values
    if parameter in ['rooms'] and unique_values < 10:
        jittered_data = clean_data + np.random.normal(0, 0.1, len(clean_data))
        plt.hist(jittered_data, bins=actual_bins, color='#2196F3', edgecolor='black', alpha=0.7)
    else:
        plt.hist(clean_data, bins=actual_bins, color='#2196F3', edgecolor='black', alpha=0.7)
    plt.grid(True, alpha=0.3, linestyle='--', color='gray')
    
    # Add statistics lines
    plt.axvline(stats['mean'], color='red', linestyle='dashed', linewidth=1, label=f"Mean: {format_axis_label(stats['mean'], True)}")
    plt.axvline(stats['median'], color='green', linestyle='dashed', linewidth=1, label=f"Median: {format_axis_label(stats['median'], True)}")
    
    # Set title and labels
    display_title = title if title else f"{parameter.capitalize()} Distribution"
    plt.title(display_title, pad=20, fontsize=14, fontweight='bold')
    
    # Set appropriate x-axis label based on parameter
    if parameter == 'price':
        plt.xlabel("Price (₽)", labelpad=10)
        include_rub = True
    elif parameter == 'area':
        plt.xlabel("Area (m²)", labelpad=10)
        include_rub = False
    elif parameter == 'rooms':
        plt.xlabel("Number of Rooms", labelpad=10)
        include_rub = False
    elif parameter == 'seller_rating':
        plt.xlabel("Seller Rating", labelpad=10)
        include_rub = False
    elif parameter == 'views':
        plt.xlabel("View Count", labelpad=10)
        include_rub = False
    else:
        plt.xlabel(parameter.capitalize(), labelpad=10)
        include_rub = False
    
    plt.ylabel("Number of Listings", labelpad=10)
    plt.legend(frameon=True, facecolor='white', shadow=True)
    
    # Save figure to a base64-encoded string
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    
    # Prepare histogram data for Chart.js
    # Use the same bins as in the matplotlib plot
    hist, bin_edges = np.histogram(clean_data, bins=actual_bins)
    
    # For discrete data with few unique values, create more readable labels
    if parameter in ['rooms'] and unique_values <= 10:
        # For room counts, use integers as labels (1, 2, 3 rooms etc.)
        labels = [f"{int(val)} {'room' if int(val)==1 else 'rooms'}" for val in sorted(clean_data.unique())]
        values = [len(clean_data[clean_data == val]) for val in sorted(clean_data.unique())]
        chart_data = {
            'labels': labels,
            'values': values
        }
    else:
        # For continuous data, use the standard approach
        chart_data = {
            'labels': [format_axis_label((bin_edges[i] + bin_edges[i+1])/2, include_rub) for i in range(len(bin_edges)-1)],
            'values': hist.tolist()
        }
    
    return {
        'image_base64': image_base64,
        'statistics': stats,
        'chart_data': chart_data
    }

def analyze_data(data_id, analysis_params):
    """
    Analyzes scraped data with the given parameters
    
    Args:
        data_id (int): ID of the scraped data to analyze
        analysis_params (dict): Parameters for analysis with keys:
            - parameter (str): Parameter to analyze
            - title (str, optional): Custom title for visualization
            - bins (int, optional): Number of bins for histogram
            
    Returns:
        dict: Result of the analysis operation with keys:
            - success (bool): Whether the analysis was successful
            - analysis_id (int, optional): ID of the stored analysis if successful
            - error (str, optional): Error message if unsuccessful
    """
    try:
        logger.info(f"Starting analysis for data ID: {data_id}")
        
        # Get scraped data from database
        scraped_data = ScrapedData.query.get(data_id)
        if not scraped_data:
            return {"success": False, "error": f"No scraped data found with ID: {data_id}"}
        
        # Parse JSON data
        data_json = json.loads(scraped_data.data)
        
        # Extract parameter to analyze
        parameter = analysis_params.get('parameter')
        title = analysis_params.get('title', '')
        bins = analysis_params.get('bins', 30)
        
        if not parameter:
            return {"success": False, "error": "No parameter specified for analysis"}
        
        # Create DataFrame from listings
        listings = data_json.get('listings', [])
        df = pd.DataFrame(listings)
        
        # Добавляем логирование для отладки
        logger.info(f"Available columns in data: {list(df.columns)}")
        logger.info(f"Sample data from first 3 listings: {listings[:3]}")
        
        # Check if parameter exists in data
        if parameter not in df.columns:
            return {"success": False, "error": f"Parameter '{parameter}' not found in the data"}
        
        # Выводим данные по параметру перед обработкой
        logger.info(f"Raw {parameter} values before extraction: {df[parameter].head().tolist()}")
        
        # Extract numeric data from parameter
        df[parameter] = df[parameter].apply(extract_number)
        
        # Выводим данные после извлечения чисел
        logger.info(f"Processed {parameter} values after extraction: {df[parameter].head().tolist()}")
        
        # Filter out missing values
        data = df[parameter].dropna()
        
        # Выводим количество действительных значений
        logger.info(f"Valid {parameter} values count: {len(data)} out of {len(df)}")
        
        if len(data) == 0:
            return {"success": False, "error": f"No valid numeric data found for parameter '{parameter}'"}
        
        # Generate visualization
        viz_result = generate_visualization(data, parameter, title, bins)
        
        # Save analysis results to database
        new_analysis = AnalysisResult(
            data_id=data_id,
            parameter=parameter,
            title=title,
            bins=bins,
            statistics=json.dumps(viz_result['statistics']),
            visualization_data=json.dumps({
                'image_base64': viz_result['image_base64'],
                'chart_data': viz_result['chart_data']
            })
        )
        db.session.add(new_analysis)
        db.session.commit()
        
        logger.info(f"Analysis completed successfully. Analysis ID: {new_analysis.id}")
        
        return {
            "success": True,
            "analysis_id": new_analysis.id
        }
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Add import here to avoid circular imports
import numpy as np
