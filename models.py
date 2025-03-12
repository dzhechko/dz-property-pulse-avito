from app import db
from datetime import datetime

class ScrapedData(db.Model):
    """Model for storing scraped data from Avito"""
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(512), nullable=False)
    data = db.Column(db.Text, nullable=False)  # JSON string of scraped data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to analysis results
    analyses = db.relationship('AnalysisResult', backref='scraped_data', lazy=True)
    
    def __repr__(self):
        return f'<ScrapedData {self.id}>'

class AnalysisResult(db.Model):
    """Model for storing analysis results"""
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, db.ForeignKey('scraped_data.id'), nullable=False)
    parameter = db.Column(db.String(128), nullable=False)
    title = db.Column(db.String(256))
    bins = db.Column(db.Integer, default=30)
    statistics = db.Column(db.Text, nullable=False)  # JSON string of statistics
    visualization_data = db.Column(db.Text, nullable=False)  # JSON string of visualization data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult {self.id} - {self.parameter}>'
