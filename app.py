import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
import docx
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
from translate import Translator
from fpdf import FPDF
import io
import base64
from fpdf import FPDF
from datetime import datetime
import io
import plotly.io as pio

from auth import check_usage_limits, init_session_state, show_subscription_status, show_upgrade_popup

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Supported languages
LANGUAGES = {
    'English': 'en',
    'Spanish': 'es',
    'French': 'fr',
    'German': 'de',
    'Chinese': 'zh',
    'Japanese': 'ja'
}

def translate_text(text, target_lang):
    """Translate text to target language"""
    try:
        translator = Translator(to_lang=target_lang)
        chunks = [text[i:i+500] for i in range(0, len(text), 500)]
        translated_text = ""
        for chunk in chunks:
            translated_text += translator.translate(chunk) + " "
        return translated_text
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        return text

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"PDF extraction error: {str(e)}")
        return ""

def extract_text_from_docx(docx_file):
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"DOCX extraction error: {str(e)}")
        return ""

def analyze_contract_score(text):
    """Calculate dynamic contract score using Gemini model's analysis"""
    prompt = f"""
    You are a contract analysis expert. Analyze this contract and provide a detailed score evaluation.
    Consider the following aspects:
    
    1. Clarity (How clear and unambiguous is the language?)
    2. Completeness (Are all essential elements present?)
    3. Fairness (Is the contract balanced between parties?)
    4. Risk Management (How well are risks addressed and mitigated?)
    5. Compliance (Does it meet legal and regulatory requirements?)
    
    For each aspect:
    - Evaluate carefully and provide a score out of 100
    - Consider both strengths and weaknesses
    - Base scores on specific contract elements
    
    Calculate the overall score as a weighted average:
    - Clarity: 25%
    - Completeness: 20%
    - Fairness: 20%
    - Risk Management: 20%
    - Compliance: 15%
    
    Return only a JSON object in this exact format:
    {{
        "overall_score": <weighted_average>,
        "score_breakdown": {{
            "clarity": <score>,
            "completeness": <score>,
            "fairness": <score>,
            "risk_management": <score>,
            "compliance": <score>
        }},
        "summary": "<brief explanation of scores with specific references to contract content>"
    }}

    Contract text: {text}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:-3]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:-3]
            
        result = json.loads(cleaned_text)
        
        required_keys = ["overall_score", "score_breakdown", "summary"]
        required_scores = ["clarity", "completeness", "fairness", "risk_management", "compliance"]
        
        if not all(key in result for key in required_keys):
            raise ValueError("Missing required keys in response")
        if not all(score in result["score_breakdown"] for score in required_scores):
            raise ValueError("Missing required scores in breakdown")
            
        if not (0 <= result["overall_score"] <= 100):
            raise ValueError("Overall score out of range")
        for score in result["score_breakdown"].values():
            if not (0 <= score <= 100):
                raise ValueError("Component score out of range")
                
        return result
        
    except Exception as e:
        st.error(f"Score analysis error: {str(e)}")
        return {
            "overall_score": 0,
            "score_breakdown": {
                "clarity": 0,
                "completeness": 0,
                "fairness": 0,
                "risk_management": 0,
                "compliance": 0
            },
            "summary": "Error analyzing contract. Please try again."
        }

def analyze_risks_and_opportunities(text):
    """Analyze contract risks and opportunities dynamically using Gemini model"""
    prompt = f"""
    You are an expert contract analyst. Perform a detailed analysis of this contract to identify specific risks and opportunities.
    Focus on actual content and provide concrete examples from the contract text.
    
    For each category below:
    1. Identify specific instances from the contract
    2. Evaluate their significance
    3. Provide specific references to relevant sections
    4. Suggest practical actions
    
    Return only a JSON object in this exact format:
    {{
        "risks": {{
            "legal_risks": {{
                "level": "<choose: High/Medium/Low based on severity>",
                "description": "<specific legal risks identified from contract text>",
                "potential_impact": "<concrete consequences>",
                "mitigation_suggestions": "<actionable steps based on identified risks>"
            }},
            "financial_risks": {{
                "level": "<High/Medium/Low>",
                "description": "<specific financial risks from contract terms>",
                "potential_impact": "<quantifiable impact where possible>",
                "mitigation_suggestions": "<practical financial safeguards>"
            }},
            "operational_risks": {{
                "level": "<High/Medium/Low>",
                "description": "<specific operational challenges found>",
                "potential_impact": "<business impact details>",
                "mitigation_suggestions": "<operational solutions>"
            }}
        }},
        "opportunities": {{
            "business_opportunities": {{
                "level": "<High/Medium/Low value potential>",
                "description": "<specific business advantages identified>",
                "potential_value": "<quantifiable benefits where possible>",
                "action_items": "<concrete steps to capitalize>"
            }},
            "strategic_opportunities": {{
                "level": "<High/Medium/Low>",
                "description": "<strategic advantages found>",
                "potential_value": "<long-term benefits>",
                "action_items": "<strategic actions to take>"
            }},
            "operational_opportunities": {{
                "level": "<High/Medium/Low>",
                "description": "<efficiency/improvement opportunities>",
                "potential_value": "<operational benefits>",
                "action_items": "<specific implementation steps>"
            }}
        }}
    }}

    Contract text: {text}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:-3]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:-3]
            
        result = json.loads(cleaned_text)
        
        required_categories = {
            "risks": ["legal_risks", "financial_risks", "operational_risks"],
            "opportunities": ["business_opportunities", "strategic_opportunities", "operational_opportunities"]
        }
        
        required_fields = ["level", "description", "potential_impact", "mitigation_suggestions"]
        opportunity_fields = ["level", "description", "potential_value", "action_items"]
        
        if not all(category in result for category in required_categories):
            raise ValueError("Missing main categories")
            
        for risk_type in required_categories["risks"]:
            if risk_type not in result["risks"]:
                raise ValueError(f"Missing risk category: {risk_type}")
            if not all(field in result["risks"][risk_type] for field in required_fields):
                raise ValueError(f"Missing fields in {risk_type}")
                
        for opp_type in required_categories["opportunities"]:
            if opp_type not in result["opportunities"]:
                raise ValueError(f"Missing opportunity category: {opp_type}")
            if not all(field in result["opportunities"][opp_type] for field in opportunity_fields):
                raise ValueError(f"Missing fields in {opp_type}")
                
        valid_levels = ["High", "Medium", "Low"]
        for category in result["risks"].values():
            if category["level"] not in valid_levels:
                raise ValueError("Invalid risk level")
        for category in result["opportunities"].values():
            if category["level"] not in valid_levels:
                raise ValueError("Invalid opportunity level")
                
        return result
        
    except Exception as e:
        st.error(f"Risk and opportunities analysis error: {str(e)}")
        default_risk = {
            "level": "Low",
            "description": "Analysis failed",
            "potential_impact": "Unable to assess",
            "mitigation_suggestions": "Please try analysis again"
        }
        default_opportunity = {
            "level": "Low",
            "description": "Analysis failed",
            "potential_value": "Unable to assess",
            "action_items": "Please try analysis again"
        }
        
        return {
            "risks": {
                "legal_risks": default_risk.copy(),
                "financial_risks": default_risk.copy(),
                "operational_risks": default_risk.copy()
            },
            "opportunities": {
                "business_opportunities": default_opportunity.copy(),
                "strategic_opportunities": default_opportunity.copy(),
                "operational_opportunities": default_opportunity.copy()
            }
        }

def create_risk_opportunity_charts(analysis_data):
    """Create dynamic visualizations for risks and opportunities based on actual analysis"""
    
    risk_levels = {"High": 3, "Medium": 2, "Low": 1}
    
    risk_scores = []
    risk_count = {"High": 0, "Medium": 0, "Low": 0}
    for risk_type, details in analysis_data["risks"].items():
        level = details["level"]
        risk_scores.append(risk_levels[level])
        risk_count[level] += 1
    
    opp_scores = []
    opp_count = {"High": 0, "Medium": 0, "Low": 0}
    for opp_type, details in analysis_data["opportunities"].items():
        level = details["level"]
        opp_scores.append(risk_levels[level])
        opp_count[level] += 1
    
    total_risk_weight = sum(risk_scores)
    total_opp_weight = sum(opp_scores)
    total_weight = total_risk_weight + total_opp_weight
    
    if total_weight == 0:
        risk_percentage = 50
        opp_percentage = 50
    else:
        risk_percentage = (total_risk_weight / total_weight) * 100
        opp_percentage = (total_opp_weight / total_weight) * 100
    
    pie_data = []
    
    for level in ["High", "Medium", "Low"]:
        if risk_count[level] > 0:
            pie_data.append({
                'Category': f'Risks ({level})',
                'Percentage': (risk_count[level] * risk_levels[level] / total_weight) * 100,
                'Type': 'Risk'
            })
    
    for level in ["High", "Medium", "Low"]:
        if opp_count[level] > 0:
            pie_data.append({
                'Category': f'Opportunities ({level})',
                'Percentage': (opp_count[level] * risk_levels[level] / total_weight) * 100,
                'Type': 'Opportunity'
            })
    
    pie_df = pd.DataFrame(pie_data)
    
    pie_fig = px.pie(
        pie_df,
        values='Percentage',
        names='Category',
        title='Distribution of Risks and Opportunities',
        color='Type',
        color_discrete_map={
            'Risk': '#FF6B6B',
            'Opportunity': '#4ECDC4'
        }
    )
    
    pie_fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hole=0.4,
        pull=[0.1 if 'High' in cat else 0 for cat in pie_df['Category']]
    )
    
    radar_fig = go.Figure()
    
    risk_categories = list(analysis_data['risks'].keys())
    risk_values = [risk_levels[analysis_data['risks'][cat]['level']] for cat in risk_categories]
    
    radar_fig.add_trace(go.Scatterpolar(
        r=risk_values,
        theta=[cat.replace('_', ' ').title() for cat in risk_categories],
        name='Risks',
        fill='toself',
        fillcolor='rgba(255, 107, 107, 0.5)',
        line=dict(color='#FF6B6B')
    ))
    
    opp_categories = list(analysis_data['opportunities'].keys())
    opp_values = [risk_levels[analysis_data['opportunities'][cat]['level']] for cat in opp_categories]
    
    radar_fig.add_trace(go.Scatterpolar(
        r=opp_values,
        theta=[cat.replace('_', ' ').title() for cat in opp_categories],
        name='Opportunities',
        fill='toself',
        fillcolor='rgba(78, 205, 196, 0.5)',
        line=dict(color='#4ECDC4')
    ))
    
    radar_fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 3],
                ticktext=['', 'Low', 'Medium', 'High'],
                tickvals=[0, 1, 2, 3],
                tickmode='array'
            )
        ),
        showlegend=True,
        title={
            'text': 'Risk and Opportunity Assessment',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        }
    )
    
    return pie_fig, radar_fig

def analyze_key_clauses(text):
    """Analyze key clauses and provide recommendations"""
    prompt = f"""
    Analyze this contract and provide key clauses and recommendations in the following EXACT JSON format:
    {{
        "key_clauses": {{
            "critical_clauses": [
                {{
                    "title": "clause title",
                    "summary": "brief summary",
                    "importance": "High/Medium/Low"
                }}
            ],
            "notable_provisions": [
                {{
                    "title": "provision title",
                    "summary": "brief summary",
                    "impact": "description"
                }}
            ]
        }},
        "recommendations": [
            {{
                "category": "category name",
                "suggestion": "detailed suggestion",
                "priority": "High/Medium/Low"
            }}
        ]
    }}
    Contract text: {text}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:-3]
        return json.loads(cleaned_text)
    except Exception as e:
        return {"key_clauses": {"critical_clauses": [], "notable_provisions": []}, "recommendations": []}
    
def create_risk_opportunity_charts(analysis_data):
    """Create dynamic visualizations for risks and opportunities based on actual analysis"""
    
    # Risk level mapping
    risk_levels = {"High": 3, "Medium": 2, "Low": 1}
    
    # Calculate risk and opportunity scores
    risk_scores = []
    risk_count = {"High": 0, "Medium": 0, "Low": 0}
    for risk_type, details in analysis_data["risks"].items():
        level = details["level"]
        risk_scores.append(risk_levels[level])
        risk_count[level] += 1
    
    opp_scores = []
    opp_count = {"High": 0, "Medium": 0, "Low": 0}
    for opp_type, details in analysis_data["opportunities"].items():
        level = details["level"]
        opp_scores.append(risk_levels[level])
        opp_count[level] += 1
    
    # Calculate weighted risk and opportunity percentages
    total_risk_weight = sum(risk_scores)
    total_opp_weight = sum(opp_scores)
    total_weight = total_risk_weight + total_opp_weight
    
    if total_weight == 0:  # Prevent division by zero
        risk_percentage = 50
        opp_percentage = 50
    else:
        risk_percentage = (total_risk_weight / total_weight) * 100
        opp_percentage = (total_opp_weight / total_weight) * 100
    
    # Create pie chart with detailed breakdown
    pie_data = []
    
    # Add risk breakdown
    for level in ["High", "Medium", "Low"]:
        if risk_count[level] > 0:
            pie_data.append({
                'Category': f'Risks ({level})',
                'Percentage': (risk_count[level] * risk_levels[level] / total_weight) * 100,
                'Type': 'Risk'
            })
    
    # Add opportunity breakdown
    for level in ["High", "Medium", "Low"]:
        if opp_count[level] > 0:
            pie_data.append({
                'Category': f'Opportunities ({level})',
                'Percentage': (opp_count[level] * risk_levels[level] / total_weight) * 100,
                'Type': 'Opportunity'
            })
    
    pie_df = pd.DataFrame(pie_data)
    
    # Create enhanced pie chart
    pie_fig = px.pie(
        pie_df,
        values='Percentage',
        names='Category',
        title='Distribution of Risks and Opportunities',
        color='Type',
        color_discrete_map={
            'Risk': '#FF6B6B',
            'Opportunity': '#4ECDC4'
        }
    )
    
    # Update pie chart layout
    pie_fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hole=0.4,
        pull=[0.1 if 'High' in cat else 0 for cat in pie_df['Category']]
    )
    
    # Create radar chart with separate risk and opportunity traces
    radar_fig = go.Figure()
    
    # Add risk trace
    risk_categories = list(analysis_data['risks'].keys())
    risk_values = [risk_levels[analysis_data['risks'][cat]['level']] for cat in risk_categories]
    
    radar_fig.add_trace(go.Scatterpolar(
        r=risk_values,
        theta=[cat.replace('_', ' ').title() for cat in risk_categories],
        name='Risks',
        fill='toself',
        fillcolor='rgba(255, 107, 107, 0.5)',
        line=dict(color='#FF6B6B')
    ))
    
    # Add opportunity trace
    opp_categories = list(analysis_data['opportunities'].keys())
    opp_values = [risk_levels[analysis_data['opportunities'][cat]['level']] for cat in opp_categories]
    
    radar_fig.add_trace(go.Scatterpolar(
        r=opp_values,
        theta=[cat.replace('_', ' ').title() for cat in opp_categories],
        name='Opportunities',
        fill='toself',
        fillcolor='rgba(78, 205, 196, 0.5)',
        line=dict(color='#4ECDC4')
    ))
    
    # Update radar chart layout
    radar_fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 3],
                ticktext=['', 'Low', 'Medium', 'High'],
                tickvals=[0, 1, 2, 3],
                tickmode='array'
            )
        ),
        showlegend=True,
        title={
            'text': 'Risk and Opportunity Assessment',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        }
    )
    
    return pie_fig, radar_fig



def get_executive_summary(contract_text):
    """Generate a structured executive summary using Gemini model"""
    prompt = f"""
    As a contract analysis expert, provide a structured executive summary of this contract.
    Focus on the following aspects and provide ONLY a JSON response in this exact format:
    {{
        "overview": "2-3 sentences describing the main purpose and parties of the contract",
        "key_points": [
            "3-4 most important points from the contract"
        ],
        "critical_dates": [
            "List of important dates and deadlines"
        ],
        "major_obligations": {{
            "party_a": [
                "Key obligations of first party"
            ],
            "party_b": [
                "Key obligations of second party"
            ]
        }},
        "risk_summary": "2-3 sentences highlighting the most significant risks",
        "recommendation": "1-2 sentences of primary recommendation"
    }}

    Contract text: {contract_text}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:-3]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:-3]
            
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return {
            "overview": "Summary generation failed",
            "key_points": ["Error analyzing contract"],
            "critical_dates": ["Not available"],
            "major_obligations": {
                "party_a": ["Not available"],
                "party_b": ["Not available"]
            },
            "risk_summary": "Unable to analyze risks",
            "recommendation": "Please try analysis again"
        }

def generate_pdf_report(contract_text, score_data, risk_opp_data, clause_data, figures=None):
    """Generate PDF report with analysis results and visualizations"""
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Contract Analysis Report', 0, 1, 'C')
            self.ln(10)
            
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Page {self.page_no()}', 0, 0, 'C')

    # Generate executive summary
    executive_summary = get_executive_summary(contract_text)
    
    # Create PDF
    pdf = PDF()
    pdf.add_page()
    
    # Executive Summary Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Executive Summary', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 10, executive_summary['overview'])
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Key Points:', 0, 1)
    pdf.set_font('Arial', '', 11)
    for point in executive_summary['key_points']:
        pdf.multi_cell(0, 10, f"- {point}")
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Critical Dates:', 0, 1)
    pdf.set_font('Arial', '', 11)
    for date in executive_summary['critical_dates']:
        pdf.multi_cell(0, 10, f"- {date}")
    
    # Score Analysis
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Contract Score Analysis', 0, 1)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Overall Score: {score_data.get('overall_score', 'N/A')}/100", 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', '', 11)
    for metric, score in score_data.get('score_breakdown', {}).items():
        pdf.cell(0, 10, f"- {metric.replace('_', ' ').title()}: {score}/100", 0, 1)
    
    # Major Obligations
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Major Obligations', 0, 1)
    
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Party A:', 0, 1)
    pdf.set_font('Arial', '', 11)
    for obligation in executive_summary['major_obligations']['party_a']:
        pdf.multi_cell(0, 10, f"- {obligation}")
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 10, 'Party B:', 0, 1)
    pdf.set_font('Arial', '', 11)
    for obligation in executive_summary['major_obligations']['party_b']:
        pdf.multi_cell(0, 10, f"- {obligation}")
    
    # Risk Analysis
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Risk Analysis', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 10, executive_summary['risk_summary'])
    
    pdf.ln(5)
    for risk_type, details in risk_opp_data.get('risks', {}).items():
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, risk_type.replace('_', ' ').title(), 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 10, f"Level: {details.get('level', 'N/A')}")
        pdf.multi_cell(0, 10, f"Description: {details.get('description', 'N/A')}")
        pdf.multi_cell(0, 10, f"Impact: {details.get('potential_impact', 'N/A')}")
        pdf.multi_cell(0, 10, f"Mitigation: {details.get('mitigation_suggestions', 'N/A')}")
        pdf.ln(5)
    
    # Opportunities Analysis
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Opportunities Analysis', 0, 1)
    
    for opp_type, details in risk_opp_data.get('opportunities', {}).items():
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 10, opp_type.replace('_', ' ').title(), 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 10, f"Level: {details.get('level', 'N/A')}")
        pdf.multi_cell(0, 10, f"Description: {details.get('description', 'N/A')}")
        pdf.multi_cell(0, 10, f"Value: {details.get('potential_value', 'N/A')}")
        pdf.multi_cell(0, 10, f"Actions: {details.get('action_items', 'N/A')}")
        pdf.ln(5)
    
    # Recommendations
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Recommendations', 0, 1)
    
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 10, executive_summary['recommendation'])
    
    # Add visualizations if provided
    if figures:
        for fig in figures:
            try:
                # Convert Plotly figure to PNG bytes
                img_bytes = fig.to_image(format="png")
                
                # Save to temporary file
                temp_file = "temp_chart.png"
                with open(temp_file, "wb") as f:
                    f.write(img_bytes)
                
                # Add new page and image
                pdf.add_page()
                pdf.image(temp_file, x=10, y=30, w=190)
                
                # Clean up
                os.remove(temp_file)
            except Exception as e:
                print(f"Error adding visualization: {str(e)}")
                continue
    
    try:
        # Return PDF as bytes
        return pdf.output(dest='S').encode('latin-1', errors='ignore')
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

def ask_question(text, question, context=None):
    """Enhanced Q&A function with context tracking"""
    try:
        prompt = f"""
        Based on this contract: {text}
        
        Previous context: {context if context else 'None'}
        
        Please answer this question: {question}
        
        Provide a clear, direct answer with specific references to relevant sections of the contract when applicable.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Q&A error: {str(e)}")
        return "Failed to get answer. Please try again."

def main():
    st.set_page_config(page_title="Contract Analysis System", layout="wide")
    
    # Initialize session state for authentication and usage tracking
    init_session_state()
    
    st.title("Advanced Contract Analysis System")
    st.write("Upload your contracts for AI-powered analysis")
    
    # Language selection
    selected_language = st.selectbox("Select Language", list(LANGUAGES.keys()))
    
    # Session state initialization for Q&A
    if 'qa_history' not in st.session_state:
        st.session_state.qa_history = []
    
    # File upload
    uploaded_files = st.file_uploader(
        "Choose contract file(s)", 
        type=['pdf', 'docx'], 
        accept_multiple_files=True,
        help="Upload PDF or DOCX files for analysis"
    )
    
    if uploaded_files:
        contract_texts = []
        for file in uploaded_files:
            if file.type == "application/pdf":
                text = extract_text_from_pdf(file)
            else:
                text = extract_text_from_docx(file)
            contract_texts.append(text)
        
        # Create tabs for different analyses
        tabs = st.tabs(["Overview", "Risks & Opportunities", "Key Clauses", "Comparison", "Q&A", "Report"])
        
        with tabs[0]:
            st.header("Contract Overview")
            if st.button("Analyze Overview"):
                if check_usage_limits('analysis'):
                    for i, text in enumerate(contract_texts):
                        st.subheader(f"Contract {i+1}")
                        with st.spinner("Analyzing..."):
                            score_data = analyze_contract_score(text)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Overall Score", f"{score_data['overall_score']}/100")
                                
                                st.subheader("Score Breakdown")
                                for metric, score in score_data["score_breakdown"].items():
                                    st.metric(metric.title(), f"{score}/100")
                            
                            with col2:
                                gauge_fig = go.Figure(go.Indicator(
                                    mode="gauge+number",
                                    value=score_data['overall_score'],
                                    title={'text': "Contract Score"},
                                    gauge={'axis': {'range': [0, 100]},
                                           'bar': {'color': "#4ECDC4"},
                                           'steps': [
                                               {'range': [0, 50], 'color': "#FF6B6B"},
                                               {'range': [50, 75], 'color': "#FFD93D"},
                                               {'range': [75, 100], 'color': "#4ECDC4"}
                                           ]}
                                ))
                                st.plotly_chart(gauge_fig)
                            
                            st.markdown("### Analysis Summary")
                            st.write(score_data["summary"])
        
        with tabs[1]:
            st.header("Risks & Opportunities Assessment")
            if st.button("Analyze Risks & Opportunities"):
                if check_usage_limits('analysis'):
                    for i, text in enumerate(contract_texts):
                        st.subheader(f"Contract {i+1}")
                        with st.spinner("Analyzing risks and opportunities..."):
                            analysis_data = analyze_risks_and_opportunities(text)
                            
                            pie_fig, radar_fig = create_risk_opportunity_charts(analysis_data)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.plotly_chart(pie_fig, use_container_width=True)
                            with col2:
                                st.plotly_chart(radar_fig, use_container_width=True)
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("Risks")
                                for risk_type, details in analysis_data["risks"].items():
                                    with st.expander(f"{risk_type.replace('_', ' ').title()} ({details['level']})"):
                                        st.markdown(f"**Description:** {details['description']}")
                                        st.markdown(f"**Impact:** {details['potential_impact']}")
                                        st.markdown(f"**Mitigation:** {details['mitigation_suggestions']}")
                            
                            with col2:
                                st.subheader("Opportunities")
                                for opp_type, details in analysis_data["opportunities"].items():
                                    with st.expander(f"{opp_type.replace('_', ' ').title()} ({details['level']})"):
                                        st.markdown(f"**Description:** {details['description']}")
                                        st.markdown(f"**Value:** {details['potential_value']}")
                                        st.markdown(f"**Actions:** {details['action_items']}")
        
        with tabs[2]:
            st.header("Key Clauses Analysis")
            if st.button("Analyze Key Clauses"):
                if check_usage_limits('analysis'):
                    for i, text in enumerate(contract_texts):
                        st.subheader(f"Contract {i+1}")
                        with st.spinner("Analyzing key clauses..."):
                            clause_data = analyze_key_clauses(text)
                            
                            st.subheader("Critical Clauses")
                            for clause in clause_data["key_clauses"]["critical_clauses"]:
                                with st.expander(f"{clause['title']} (Importance: {clause['importance']})"):
                                    st.write(clause["summary"])
                            
                            st.subheader("Recommendations")
                            for rec in clause_data["recommendations"]:
                                with st.expander(f"{rec['category']} (Priority: {rec['priority']})"):
                                    st.write(rec["suggestion"])
        
        with tabs[3]:
            st.header("Contract Comparison")
            if len(contract_texts) >= 2:
                if st.button("Compare Contracts"):
                    if check_usage_limits('analysis'):
                        with st.spinner("Comparing contracts..."):
                            scores = []
                            analyses = []
                            for text in contract_texts[:2]:
                                scores.append(analyze_contract_score(text))
                                analyses.append(analyze_risks_and_opportunities(text))
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.subheader("Score Comparison")
                                score_comparison = pd.DataFrame({
                                    'Metric': ['Overall'] + list(scores[0]['score_breakdown'].keys()),
                                    'Contract 1': [scores[0]['overall_score']] + list(scores[0]['score_breakdown'].values()),
                                    'Contract 2': [scores[1]['overall_score']] + list(scores[1]['score_breakdown'].values())
                                })
                                fig = px.bar(score_comparison, x='Metric', y=['Contract 1', 'Contract 2'],
                                           title="Score Comparison", barmode='group')
                                st.plotly_chart(fig)
                            
                            with col2:
                                st.subheader("Risk Profile Comparison")
                                risk_comparison = go.Figure()
                                for i, analysis in enumerate(analyses, 1):
                                    risk_levels = [{'High': 3, 'Medium': 2, 'Low': 1}[risk['level']] 
                                                 for risk in analysis['risks'].values()]
                                    risk_comparison.add_trace(go.Scatterpolar(
                                        r=risk_levels,
                                        theta=list(analysis['risks'].keys()),
                                        name=f'Contract {i}'
                                    ))
                                risk_comparison.update_layout(title="Risk Profile Comparison")
                                st.plotly_chart(risk_comparison)
            else:
                st.warning("Please upload at least two contracts for comparison")
        
        with tabs[4]:
            st.header("Question & Answer")
            if check_usage_limits('queries'):
                selected_contract = st.selectbox(
                    "Select Contract for Q&A",
                    range(len(contract_texts)),
                    format_func=lambda x: f"Contract {x+1}"
                )
                
                question_templates = [
                    "What are the key deadlines?",
                    "What are the main financial obligations?",
                    "What are the termination conditions?",
                    "What are the liability clauses?",
                    "Custom question"
                ]
                
                template_choice = st.selectbox("Choose question type:", question_templates)
                
                if template_choice == "Custom question":
                    question = st.text_input("Enter your question:")
                else:
                    question = template_choice
                
                if question and st.button("Ask Question"):
                    with st.spinner("Finding answer..."):
                        context = "; ".join([f"Q: {q} A: {a}" for q, a in st.session_state.qa_history[-3:]])
                        answer = ask_question(contract_texts[selected_contract], question, context)
                        
                        if selected_language != 'English':
                            answer = translate_text(answer, LANGUAGES[selected_language])
                        
                        st.session_state.qa_history.append((question, answer))
                        st.markdown("### Answer:")
                        st.markdown(answer)
                
                if st.session_state.qa_history:
                    with st.expander("Question & Answer History"):
                        for q, a in st.session_state.qa_history:
                            st.markdown(f"**Q:** {q}")
                            st.markdown(f"**A:** {a}")
                            st.markdown("---")
        
        with tabs[5]:
            st.header("Generate Report")
            if st.button("Generate Complete Report"):
                if check_usage_limits('reports'):
                    for i, text in enumerate(contract_texts):
                        with st.spinner(f"Generating report for Contract {i+1}..."):
                            score_data = analyze_contract_score(text)
                            risk_opp_data = analyze_risks_and_opportunities(text)
                            clause_data = analyze_key_clauses(text)
                            
                            pie_fig, radar_fig = create_risk_opportunity_charts(risk_opp_data)
                            
                            pdf_bytes = generate_pdf_report(
                                text,
                                score_data,
                                risk_opp_data,
                                clause_data,
                                [pie_fig, radar_fig]
                            )
                            
                            if pdf_bytes:
                                st.download_button(
                                    label=f"Download Report (Contract {i+1})",
                                    data=pdf_bytes,
                                    file_name=f"contract_analysis_report_{i+1}.pdf",
                                    mime="application/pdf"
                                )
                            else:
                                st.error("Failed to generate PDF report")

  

if __name__ == "__main__":
    main()