import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import json

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default-dev-secret-key")

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///avito_data.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database
db.init_app(app)

with app.app_context():
    # Import models after db is defined
    from models import ScrapedData, AnalysisResult
    db.create_all()

# Import routes after models and db setup
from scraper import scrape_avito_data
from analyzer import analyze_data, get_analysis_parameters, generate_visualization

@app.route('/')
def index():
    """Render the main page"""
    analysis_params = get_analysis_parameters()
    return render_template('index.html', analysis_params=analysis_params)

@app.route('/scrape', methods=['POST'])
def scrape():
    """Handle scraping request"""
    url = request.form.get('url')
    if not url:
        flash('Please provide a valid URL', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Store request in session to maintain state
        session['scrape_url'] = url
        
        # Start scraping process
        result = scrape_avito_data(url)
        
        if result['success']:
            session['data_id'] = result['data_id']
            
            # Get listing count to display to user
            try:
                scraped_data = ScrapedData.query.get(result['data_id'])
                data_json = json.loads(scraped_data.data)
                listing_count = len(data_json.get('listings', []))
                
                # Save listing count in session for display on multiple pages
                session['listing_count'] = listing_count
                
                flash(f'Scraping completed successfully! Found {listing_count} listings.', 'success')
            except Exception as e:
                app.logger.error(f"Error getting listing count: {str(e)}")
                flash('Scraping completed successfully!', 'success')
            
            return redirect(url_for('index', _anchor='analysis-section'))
        else:
            flash(f'Error during scraping: {result["error"]}', 'danger')
            return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Scraping error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/analyze', methods=['POST'])
def analyze():
    """Handle analysis request"""
    data_id = session.get('data_id')
    if not data_id:
        flash('No data available for analysis. Please scrape data first.', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Get analysis parameters from form
        parameter = request.form.get('parameter')
        title = request.form.get('title', '')
        bins = request.form.get('bins', 30)
        
        # Try to convert bins to integer
        try:
            bins = int(bins)
        except ValueError:
            bins = 30
        
        # Create analysis parameters
        analysis_params = {
            'parameter': parameter,
            'title': title,
            'bins': bins
        }
        
        # Run analysis
        result = analyze_data(data_id, analysis_params)
        
        if result['success']:
            session['analysis_id'] = result['analysis_id']
            return redirect(url_for('results'))
        else:
            flash(f'Error during analysis: {result["error"]}', 'danger')
            return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Analysis error: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    """Show analysis results"""
    analysis_id = session.get('analysis_id')
    if not analysis_id:
        flash('No analysis results available. Please perform analysis first.', 'warning')
        return redirect(url_for('index'))
    
    try:
        # Retrieve analysis result from database
        result = AnalysisResult.query.get(analysis_id)
        if not result:
            flash('Analysis result not found', 'danger')
            return redirect(url_for('index'))
        
        # Parse statistics from JSON
        statistics = json.loads(result.statistics)
        visualization_data = json.loads(result.visualization_data)
        
        return render_template('results.html', 
                              result=result, 
                              statistics=statistics,
                              visualization_data=visualization_data)
    except Exception as e:
        app.logger.error(f"Error displaying results: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/api/data/<int:data_id>')
def get_data(data_id):
    """API endpoint to retrieve scraped data"""
    try:
        data = ScrapedData.query.get(data_id)
        if not data:
            return jsonify({'error': 'Data not found'}), 404
        
        return jsonify({
            'id': data.id,
            'url': data.url,
            'data': json.loads(data.data),
            'created_at': data.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/<int:analysis_id>')
def get_analysis(analysis_id):
    """API endpoint to retrieve analysis results"""
    try:
        analysis = AnalysisResult.query.get(analysis_id)
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
        
        return jsonify({
            'id': analysis.id,
            'data_id': analysis.data_id,
            'parameter': analysis.parameter,
            'title': analysis.title,
            'bins': analysis.bins,
            'statistics': json.loads(analysis.statistics),
            'visualization_data': json.loads(analysis.visualization_data),
            'created_at': analysis.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
