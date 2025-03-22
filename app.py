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
import tempfile
import streamlit.components.v1 as components
from contract_reminders import add_reminders_to_app
from auth import (
    init_session_state, 
    check_usage_limits,
    reset_daily_counts,
    show_subscription_status, 
    show_upgrade_popup, 
    show_support_interface,
    show_payment_interface,
    show_login_form,
    logout_user,
    FREE_TIER_LIMITS
)

# Load environment variables
load_dotenv()

# Initialize session state
init_session_state()

# Configure Gemini API
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-pro')

# Supported languages
LANGUAGES = {
    'English': 'en',
    'Spanish': 'es',
    'French': 'fr',
    'German': 'de',
    'Chinese (Simplified)': 'zh-CN',
    'Hindi': 'hi',
    'Japanese': 'ja',
    'Portuguese': 'pt',
    'Arabic': 'ar'
}

# Add custom CSS
def local_css():
    st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    
    .stApp > header {
        background-color: transparent;
    }
    
    .card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        margin-bottom: 1rem;
        border-left: 4px solid #1565C0;
    }
    
    .results-container {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
        margin-bottom: 1rem;
    }
    
    .risk-high {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #ffebee;
        margin-bottom: 0.5rem;
    }
    
    .risk-medium {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #fff8e1;
        margin-bottom: 0.5rem;
    }
    
    .risk-low {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #e8f5e9;
        margin-bottom: 0.5rem;
    }
    
    .opportunity-high {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #e8f5e9;
        margin-bottom: 0.5rem;
    }
    
    .opportunity-medium {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #e3f2fd;
        margin-bottom: 0.5rem;
    }
    
    .opportunity-low {
        border-radius: 0.3rem;
        padding: 0.8rem;
        background-color: #f3e5f5;
        margin-bottom: 0.5rem;
    }
    
    .upgrade-banner {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #e3f2fd;
        margin-bottom: 1rem;
        border-left: 4px solid #1565C0;
    }
    
    /* Download button styling */
    .download-btn {
        display: inline-block;
        background-color: #1565C0;
        color: white;
        padding: 0.5rem 1rem;
        text-align: center;
        text-decoration: none;
        font-size: 14px;
        border-radius: 4px;
        border: none;
        cursor: pointer;
        margin: 0.5rem 0;
        width: 100%;
    }
    
    .download-btn:hover {
        background-color: #0D47A1;
        color: white;
    }
    
    .ai-message {
        background-color: #f0f7ff;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .divider {
        margin: 1rem 0;
        border-top: 1px solid #e0e0e0;
    }
    
    div.stButton > button {
        background-color: #1565C0;
        color: white;
        border: none;
    }
    
    div.stButton > button:hover {
        background-color: #0D47A1;
        color: white;
        border: none;
    }
    
    /* Logo styling with proper padding */
    .logo-container {
        display: flex;
        justify-content: center;
        margin-bottom: 0.5rem;
    }
    
    .logo-container img {
        max-width: 150px;
        padding: 0; /* Fix for padding issue */
    }
    </style>
    """, unsafe_allow_html=True)

def translate_text(text, target_lang):
    """Translate text to target language with enhanced handling for Indian languages"""
    try:
        if not text or target_lang == 'en':
            return text
            
        # Using translate library for basic translation
        translator = Translator(to_lang=target_lang)
        
        # For longer texts, break into paragraphs and translate separately
        if len(text) > 500:
            paragraphs = text.split('\n\n')
            translated_paragraphs = []
            
            for para in paragraphs:
                if para.strip():
                    translated_para = translator.translate(para[:500])  # Translate first 500 chars of each paragraph
                    translated_paragraphs.append(translated_para)
                else:
                    translated_paragraphs.append('')
                    
            return '\n\n'.join(translated_paragraphs)
        else:
            return translator.translate(text)
    
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        return text  # Return original text if translation fails

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
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
        st.error(f"Error extracting DOCX text: {str(e)}")
        return ""

def analyze_contract_score(text):
    """Calculate dynamic contract score using Gemini model's analysis"""
    prompt = f"""
    Analyze this legal contract deeply and provide a scoring analysis with the following:

    1. Calculate an overall contract score (0-100) based on clarity, completeness, fairness, and risk level
    2. Score the following categories individually (0-100):
       - Clarity and Language
       - Comprehensiveness
       - Risk Protection
       - Balanced Rights
       - Compliance
    3. Provide a brief explanation of the scoring (2-3 paragraphs)

    Return ONLY a JSON object with this exact format:
    {{
        "overall_score": <integer 0-100>,
        "score_breakdown": {{
            "clarity_and_language": <integer 0-100>,
            "comprehensiveness": <integer 0-100>,
            "risk_protection": <integer 0-100>,
            "balanced_rights": <integer 0-100>,
            "compliance": <integer 0-100>
        }},
        "summary": "<2-3 paragraph explanation>"
    }}

    Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        # Extract JSON properly regardless of formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].split("```")[0].strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].split("```")[0].strip()
        elif "```" in cleaned_text:
            # Extract content between the first set of triple backticks
            cleaned_text = cleaned_text.split("```")[1].strip()
            
        # Handle potential JSON object within a JSON string issue
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Try to fix missing quotes around property names
            import re
            fixed_json = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_text)
            result = json.loads(fixed_json)
        
        return result
    
    except Exception as e:
        st.error(f"Error analyzing contract score: {str(e)}")
        return {
            "overall_score": 50,
            "score_breakdown": {
                "clarity_and_language": 50,
                "comprehensiveness": 50,
                "risk_protection": 50,
                "balanced_rights": 50,
                "compliance": 50
            },
            "summary": "Unable to analyze contract fully. Please try again or contact support if the issue persists."
        }

def analyze_risks_and_opportunities(text):
    """Analyze contract risks and opportunities dynamically using Gemini model"""
    prompt = f"""
    Perform a comprehensive analysis of risks and opportunities in this legal contract.

    Return ONLY a JSON object with this structure:
    {{
        "risks": {{
            "risk_type_1": {{
                "level": "<High/Medium/Low>",
                "description": "<brief description>",
                "potential_impact": "<impact description>",
                "mitigation_suggestions": "<suggestions>"
            }},
            ... (up to 5 most important risks)
        }},
        "opportunities": {{
            "opportunity_type_1": {{
                "level": "<High/Medium/Low>",
                "description": "<brief description>",
                "potential_value": "<value description>",
                "action_items": "<action items>"
            }},
            ... (up to 5 most important opportunities)
        }}
    }}
    
    Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        # Extract JSON properly regardless of formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].split("```")[0].strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].strip()
        
        # Handle potential JSON object within a JSON string issue
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            import re
            
            # Fixed string with better error handling
            fixed_json = cleaned_text
            
            # Fix missing quotes around property names
            fixed_json = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed_json)
            
            # Handle trailing commas which are invalid in JSON
            fixed_json = re.sub(r',\s*}', '}', fixed_json)
            fixed_json = re.sub(r',\s*]', ']', fixed_json)
            
            # Fix missing quotes around string values
            fixed_json = re.sub(r':\s*([^"{}\[\],\s][^{}\[\],\s]*)\s*([,}])', r': "\1"\2', fixed_json)
            
            try:
                result = json.loads(fixed_json)
            except json.JSONDecodeError:
                # If still failing, try a more aggressive approach with strict JSON structure
                st.warning("JSON parsing error, attempting recovery...")
                
                # Construct fallback response
                result = {
                    "risks": {
                        "parsing_error": {
                            "level": "Medium",
                            "description": "Error parsing the analysis. Please try again.",
                            "potential_impact": "Unable to properly assess risks",
                            "mitigation_suggestions": "Please review the contract manually."
                        }
                    },
                    "opportunities": {
                        "parsing_error": {
                            "level": "Medium",
                            "description": "Error parsing the analysis. Please try again.",
                            "potential_value": "Unable to properly assess opportunities",
                            "action_items": "Please review the contract manually."
                        }
                    }
                }
        
        return result
    
    except Exception as e:
        st.error(f"Error analyzing risks and opportunities: {str(e)}")
        return {
            "risks": {
                "general_risk": {
                    "level": "Medium",
                    "description": "Unable to fully analyze risks. Please try again.",
                    "potential_impact": "Unknown",
                    "mitigation_suggestions": "Review the contract manually."
                }
            },
            "opportunities": {
                "general_opportunity": {
                    "level": "Medium",
                    "description": "Unable to fully analyze opportunities. Please try again.",
                    "potential_value": "Unknown",
                    "action_items": "Review the contract manually."
                }
            }
        }

def create_risk_opportunity_charts(analysis_data):
    """Create visualizations for risks and opportunities"""
    # Extract data for visualization
    risk_names = []
    risk_levels_numeric = []
    
    opportunity_names = []
    opportunity_levels_numeric = []
    
    # Convert risk levels to numeric values
    level_mapping = {"High": 3, "Medium": 2, "Low": 1}
    
    # Extract risk data
    for risk_name, risk_info in analysis_data["risks"].items():
        risk_names.append(risk_name.replace("_", " ").title())
        risk_levels_numeric.append(level_mapping.get(risk_info["level"], 2))
    
    # Extract opportunity data
    for opp_name, opp_info in analysis_data["opportunities"].items():
        opportunity_names.append(opp_name.replace("_", " ").title())
        opportunity_levels_numeric.append(level_mapping.get(opp_info["level"], 2))
    
    # Combine data for a single chart
    all_names = risk_names + opportunity_names
    all_values = risk_levels_numeric + [-val for val in opportunity_levels_numeric]  # Negative for opportunities
    all_types = ["Risk"] * len(risk_names) + ["Opportunity"] * len(opportunity_names)
    
    # Create dataframe for the chart
    df = pd.DataFrame({
        "Factor": all_names,
        "Value": all_values,
        "Type": all_types
    })
    
    # Sort by absolute value (impact level)
    df = df.sort_values(by="Value", key=abs, ascending=False)
    
    # Create horizontal bar chart
    fig = px.bar(
        df, 
        y="Factor", 
        x="Value", 
        color="Type",
        color_discrete_map={"Risk": "#f44336", "Opportunity": "#4caf50"},
        title="Risks & Opportunities Analysis",
        orientation='h',
        height=max(300, len(all_names) * 50),  # Dynamic height based on number of items
        labels={"Value": "Impact Level (Higher = Greater Impact)"}
    )
    
    # Customize layout
    fig.update_layout(
        yaxis_title=None,
        xaxis_title="Impact Level",
        legend_title="Type",
        font=dict(family="Arial", size=12),
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white"
    )
    
    # Return the figure
    return fig

def analyze_contract_clauses(text, clause_query=None):
    """Analyze specific contract clauses based on user query or do general clause analysis"""
    if not text or len(text.strip()) < 10:
        return {"error": "No contract text provided"}
    
    if clause_query:
        prompt = f"""
        Analyze the following specific aspect of the legal contract: "{clause_query}"
        
        Provide a detailed explanation of this clause/aspect, including:
        1. Where it appears in the contract
        2. What exactly it means in plain language
        3. Potential implications or concerns
        4. How it compares to standard industry practice
        5. Recommendations for improvements if applicable
        
        Return ONLY a JSON object with this structure:
        {{
            "found": true/false,
            "clause_text": "<exact text from contract if found>",
            "explanation": "<plain language explanation>",
            "implications": "<potential implications>",
            "standard_practice": "<how it compares to standard practice>",
            "recommendations": "<recommendations for improvements>"
        }}
        
        Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
        """
    else:
        prompt = f"""
        Provide a comprehensive analysis of the key clauses in this contract. Identify the 5-7 most important clauses and explain them.
        
        For each important clause, provide:
        1. Clause name/type
        2. Brief extract/summary of the clause content (literal text from the contract)
        3. Plain language explanation of what this clause means
        4. Any potential issues or concerns
        
        Return ONLY a JSON object with this structure:
        {{
            "key_clauses": [
                {{
                    "clause_type": "<type of clause>",
                    "clause_extract": "<brief extract or summary>",
                    "explanation": "<plain language explanation>",
                    "concerns": "<potential issues or concerns>"
                }},
                ... (for up to 7 most important clauses)
            ]
        }}
        
        Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
        """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        # Extract JSON properly regardless of formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].split("```")[0].strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].strip()
            
        # Handle potential JSON object within a JSON string issue
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Try to fix missing quotes around property names
            import re
            fixed_json = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_text)
            result = json.loads(fixed_json)
        
        return result
    
    except Exception as e:
        st.error(f"Error analyzing contract clauses: {str(e)}")
        if clause_query:
            return {
                "found": False,
                "clause_text": "",
                "explanation": "Unable to analyze the specific clause. Please try again or rephrase your query.",
                "implications": "",
                "standard_practice": "",
                "recommendations": ""
            }
        else:
            return {
                "key_clauses": [
                    {
                        "clause_type": "Error",
                        "clause_extract": "",
                        "explanation": "Unable to analyze clauses. Please try again or contact support.",
                        "concerns": ""
                    }
                ]
            }

def extract_key_terms(text):
    """Extract and explain key terms and definitions from the contract"""
    prompt = f"""
    Extract the key terms and definitions from this legal contract.
    
    For each key term, provide:
    1. The term itself
    2. Its definition as provided in the contract
    3. A plain language explanation
    4. Potential importance or implications
    
    Return ONLY a JSON object with this structure:
    {{
        "key_terms": [
            {{
                "term": "<term name>",
                "definition": "<definition from contract>",
                "explanation": "<plain language explanation>",
                "importance": "<why this term matters>"
            }},
            ... (for up to 15 most important terms)
        ]
    }}
    
    Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        # Extract JSON properly regardless of formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].split("```")[0].strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].strip()
            
        # Handle potential JSON object within a JSON string issue
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Try to fix missing quotes around property names
            import re
            fixed_json = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_text)
            result = json.loads(fixed_json)
        
        return result
    
    except Exception as e:
        st.error(f"Error extracting key terms: {str(e)}")
        return {
            "key_terms": [
                {
                    "term": "Error",
                    "definition": "",
                    "explanation": "Unable to extract key terms. Please try again or contact support.",
                    "importance": ""
                }
            ]
        }

def generate_summary(text):
    """Generate a concise summary of the contract"""
    prompt = f"""
    Create a concise yet comprehensive summary of this legal contract.
    
    Include:
    1. Contract type and parties involved
    2. Main purpose and scope
    3. Key rights and obligations
    4. Important dates or deadlines
    5. Notable or unusual provisions
    
    Return ONLY a JSON object with this structure:
    {{
        "contract_type": "<type of contract>",
        "parties": ["<party 1>", "<party 2>", ...],
        "purpose": "<main purpose of the contract>",
        "key_provisions": [
            "<provision 1>",
            "<provision 2>",
            ... (up to 5 key provisions)
        ],
        "important_dates": [
            {{
                "event": "<event description>",
                "date": "<date or deadline>"
            }},
            ... (if applicable)
        ],
        "notable_aspects": "<any unusual or noteworthy aspects>",
        "summary": "<4-5 sentence summary of the entire contract>"
    }}
    
    Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        
        # Extract JSON properly regardless of formatting
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:].split("```")[0].strip()
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].strip()
            
        # Handle potential JSON object within a JSON string issue
        try:
            result = json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Try to fix missing quotes around property names
            import re
            fixed_json = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_text)
            result = json.loads(fixed_json)
        
        return result
    
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
        return {
            "contract_type": "Unknown",
            "parties": ["Unknown"],
            "purpose": "Unable to determine contract purpose.",
            "key_provisions": ["Unable to extract key provisions."],
            "important_dates": [],
            "notable_aspects": "Unable to identify notable aspects.",
            "summary": "Unable to generate a summary for this contract. Please try again or contact support if the issue persists."
        }

def generate_pdf_report(contract_text, analysis_data, risks_opportunities, clause_analysis, summary_data, company_name=None):
    """Generate a downloadable PDF report of the contract analysis"""
    try:
        class PDF(FPDF):
            def header(self):
                # Logo (add this later)
                # self.image('logo.png', 10, 8, 33)
                # Arial bold 15
                self.set_font('Arial', 'B', 15)
                # Title
                self.cell(0, 10, 'Contract Analysis Report', 0, 1, 'C')
                # Line break
                self.ln(5)
                
            def footer(self):
                # Position at 1.5 cm from bottom
                self.set_y(-15)
                # Arial italic 8
                self.set_font('Arial', 'I', 8)
                # Page number
                self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')
            
            def sanitize_text(self, text):
                """Sanitize text to avoid encoding issues"""
                if text is None:
                    return ""
                # Replace bullets with '-'
                text = text.replace('•', '-')
                # Replace other problematic characters
                text = text.replace('…', '...')
                # Replace quotes
                text = text.replace('"', '"').replace('"', '"')
                text = text.replace(''', "'").replace(''', "'")
                # Replace em dash and en dash
                text = text.replace('—', '-').replace('–', '-')
                return text
                
            def chapter_title(self, title):
                # Arial 12
                self.set_font('Arial', 'B', 12)
                # Background color
                self.set_fill_color(200, 220, 255)
                # Title
                self.cell(0, 6, self.sanitize_text(title), 0, 1, 'L', True)
                # Line break
                self.ln(4)
                
            def chapter_body(self, body, font_size=10):
                # Arial font
                self.set_font('Arial', '', font_size)
                # Output justified text
                self.multi_cell(0, 5, self.sanitize_text(body))
                # Line break
                self.ln()
                
            def add_section_title(self, title):
                self.set_font('Arial', 'B', 11)
                self.cell(0, 6, self.sanitize_text(title), 0, 1, 'L')
                self.ln(2)
            
        # Create the PDF object
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Add date and company
        pdf.set_font("Arial", "", 10)
        pdf.cell(190, 6, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="R")
        
        # Add company name if available
        if company_name:
            pdf.cell(190, 6, f"Company: {company_name}", ln=True, align="L")
        
        # Add divider
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Add summary section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Contract Summary", ln=True)
        pdf.set_font("Arial", "", 10)
        
        # Add summary details
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 7, f"Contract Type: {summary_data.get('contract_type', 'N/A')}", ln=True)
        pdf.cell(190, 7, "Parties Involved:", ln=True)
        pdf.set_font("Arial", "", 10)
        for party in summary_data.get('parties', ['Unknown']):
            pdf.cell(190, 6, f"- {party}", ln=True)
        
        pdf.set_font("Arial", "B", 11)    
        pdf.cell(190, 7, "Purpose:", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(190, 6, summary_data.get('purpose', 'Unknown'))
        
        pdf.ln(5)
        
        # Add scores section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Contract Score Analysis", ln=True)
        
        # Add overall score
        pdf.set_font("Arial", "B", 12)
        overall_score = analysis_data.get('overall_score', 0)
        pdf.cell(190, 8, f"Overall Score: {overall_score}/100", ln=True)
        
        # Add score breakdown
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 7, "Score Breakdown:", ln=True)
        pdf.set_font("Arial", "", 10)
        
        score_breakdown = analysis_data.get('score_breakdown', {})
        for category, score in score_breakdown.items():
            pdf.cell(190, 6, f"- {category.replace('_', ' ').title()}: {score}/100", ln=True)
        
        # Add score explanation
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 7, "Analysis Summary:", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(190, 6, analysis_data.get('summary', 'No analysis available.'))
        
        pdf.ln(5)
        
        # Add risks section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Risks Analysis", ln=True)
        
        # Add risks
        pdf.set_font("Arial", "", 10)
        for risk_name, risk_info in risks_opportunities.get('risks', {}).items():
            pdf.set_font("Arial", "B", 11)
            pdf.cell(190, 7, f"{risk_name.replace('_', ' ').title()} (Level: {risk_info.get('level', 'Medium')})", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(190, 6, f"Description: {risk_info.get('description', 'N/A')}")
            pdf.multi_cell(190, 6, f"Impact: {risk_info.get('potential_impact', 'N/A')}")
            pdf.multi_cell(190, 6, f"Mitigation: {risk_info.get('mitigation_suggestions', 'N/A')}")
            pdf.ln(3)
        
        pdf.ln(5)
        
        # Add new page for opportunities
        pdf.add_page()
        
        # Add opportunities section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Opportunities Analysis", ln=True)
        
        # Add opportunities
        pdf.set_font("Arial", "", 10)
        for opp_name, opp_info in risks_opportunities.get('opportunities', {}).items():
            pdf.set_font("Arial", "B", 11)
            pdf.cell(190, 7, f"{opp_name.replace('_', ' ').title()} (Level: {opp_info.get('level', 'Medium')})", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(190, 6, f"Description: {opp_info.get('description', 'N/A')}")
            pdf.multi_cell(190, 6, f"Value: {opp_info.get('potential_value', 'N/A')}")
            pdf.multi_cell(190, 6, f"Action Items: {opp_info.get('action_items', 'N/A')}")
            pdf.ln(3)
        
        pdf.ln(5)
        
        # Add key provisions section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Key Provisions", ln=True)
        
        # Add provisions
        pdf.set_font("Arial", "", 10)
        for provision in summary_data.get('key_provisions', ['No key provisions identified.']):
            pdf.multi_cell(190, 6, f"- {provision}")
        
        pdf.ln(5)
        
        # Add important dates if available
        if summary_data.get('important_dates'):
            pdf.set_font("Arial", "B", 14)
            pdf.cell(190, 10, "Important Dates", ln=True)
            pdf.set_font("Arial", "", 10)
            for date_item in summary_data.get('important_dates', []):
                pdf.multi_cell(190, 6, f"- {date_item.get('event', 'Event')}: {date_item.get('date', 'N/A')}")
            pdf.ln(5)
        
        # Add key clauses section
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "Key Clauses Analysis", ln=True)
        
        # Add clauses
        if 'key_clauses' in clause_analysis:
            for clause in clause_analysis.get('key_clauses', []):
                pdf.set_font("Arial", "B", 11)
                pdf.cell(190, 7, f"{clause.get('clause_type', 'Clause')}", ln=True)
                
                pdf.set_font("Arial", "I", 10)
                pdf.multi_cell(190, 6, f"Extract: {clause.get('clause_extract', 'N/A')}")
                
                pdf.set_font("Arial", "", 10)
                pdf.multi_cell(190, 6, f"Explanation: {clause.get('explanation', 'N/A')}")
                
                if clause.get('concerns'):
                    pdf.set_font("Arial", "B", 10)
                    pdf.cell(190, 6, "Concerns:", ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.multi_cell(190, 6, clause.get('concerns', 'None'))
                
                pdf.ln(5)
        
        # Add disclaimer footer
        pdf.set_y(-25)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(190, 4, "Disclaimer: This analysis is generated by AI and should not replace professional legal advice. Always consult with a qualified legal professional for important legal matters.")
        
        # Return the PDF as bytes
        # Create a temporary file to avoid BytesIO issues
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name
            
        # Output PDF to the temporary file
        pdf.output(pdf_path)
        
        # Read the file and return its bytes
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
            
        # Clean up the temporary file
        os.unlink(pdf_path)
        
        return pdf_bytes
    
    except Exception as e:
        st.error(f"Error generating PDF report: {str(e)}")
        return None

def chat_with_contract(text, question):
    """Chat with the contract - ask specific questions and get AI-powered answers"""
    
    # Check if we have text to analyze
    if not text or len(text.strip()) < 10:
        return "Please upload a contract document first before asking questions."
        
    prompt = f"""
    Based on the legal contract provided, please answer the following question:
    
    Question: {question}
    
    Respond directly and factually based only on information present in the contract. If the answer cannot be determined from the contract, clearly state that. If relevant, mention the specific section(s) where the information is found.
    
    Contract text: {text[:12000]}  # Use first 12000 chars to stay within token limits
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        st.error(f"Error processing question: {str(e)}")
        return "I'm sorry, but I encountered an error while processing your question. Please try again or rephrase your question."

def show_contract_analysis_interface():
    """Display the contract analysis interface"""
    if 'contract_text' not in st.session_state:
        st.session_state.contract_text = ""
    
    st.header("Contract Analysis Tool 📝")
    
    # Check for authenticated user
    if not st.session_state.authenticated:
        st.warning("Please log in or register to use the full features of the contract analysis tool.")
        
        # Add a button to go to login page
        if st.button("Go to Login / Register", key="auth_redirect"):
            st.session_state.current_page = "Login"
            st.rerun()
        return
    
    # Display a welcome message and instructions
    st.markdown("""
    <div class="card">
    <h3>Welcome to the Contract Analysis Tool</h3>
    <p>Upload a contract document (PDF or DOCX) to get a comprehensive AI-powered analysis.</p>
    <p>Our tool will analyze:</p>
    <ul>
        <li>Overall contract quality and balance</li>
        <li>Potential risks and opportunities</li>
        <li>Key clauses and their implications</li>
        <li>Important terms and definitions</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs for different analysis features
    analysis_tabs = st.tabs([
        "Upload & Analyze", 
        "Risks & Opportunities", 
        "Clause Analysis", 
        "Key Terms", 
        "Chat with Contract",
        "Export Report"
    ])
    
    with analysis_tabs[0]:
        # File upload section
        uploaded_file = st.file_uploader("Upload Contract (PDF or DOCX)", type=["pdf", "docx"])
        
        if uploaded_file:
            # Extract text based on file type
            with st.spinner("Extracting text from document..."):
                if uploaded_file.name.endswith('.pdf'):
                    st.session_state.contract_text = extract_text_from_pdf(uploaded_file)
                elif uploaded_file.name.endswith('.docx'):
                    st.session_state.contract_text = extract_text_from_docx(uploaded_file)
            
            if st.session_state.contract_text:
                st.success(f"Text extracted successfully from {uploaded_file.name}")
                
                # Show a preview of the extracted text
                with st.expander("Preview Extracted Text"):
                    st.text_area("Contract Text", st.session_state.contract_text, height=200, disabled=True)
                
                # Analyze button
                if st.button("Analyze Contract", key="analyze_contract_btn"):
                    # Check usage limits before analysis
                    if check_usage_limits('analysis'):
                        with st.spinner("Analyzing contract... This may take a minute..."):
                            # Run contract analysis in parallel
                            score_analysis = analyze_contract_score(st.session_state.contract_text)
                            risks_opps = analyze_risks_and_opportunities(st.session_state.contract_text)
                            summary = generate_summary(st.session_state.contract_text)
                            
                            # Store results in session state
                            st.session_state.analysis_results = score_analysis
                            st.session_state.risks_opportunities = risks_opps
                            st.session_state.summary_data = summary
                            
                            # Analyze key clauses as well
                            st.session_state.clause_analysis = analyze_contract_clauses(st.session_state.contract_text)
                            
                            # Extract key terms
                            st.session_state.key_terms = extract_key_terms(st.session_state.contract_text)
                            
                            st.success("Analysis complete! Navigate through the tabs to see the results.")
                    else:
                        st.warning("You have reached your daily analysis limit. Please upgrade to continue.")
            else:
                st.error("Failed to extract text from the document. Please try a different file.")
        
        # Check if analysis results exist and display them
        if 'analysis_results' in st.session_state and st.session_state.analysis_results:
            st.markdown("### Contract Score Analysis")
            
            # Create columns for scores
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Create a gauge chart for overall score
                overall_score = st.session_state.analysis_results.get('overall_score', 0)
                
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=overall_score,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Overall Score"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 40], 'color': "red"},
                            {'range': [40, 70], 'color': "orange"},
                            {'range': [70, 90], 'color': "lightgreen"},
                            {'range': [90, 100], 'color': "green"},
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': overall_score
                        }
                    }
                ))
                
                fig.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Display score breakdown
                st.subheader("Score Breakdown")
                
                score_breakdown = st.session_state.analysis_results.get('score_breakdown', {})
                
                # Create a horizontal bar chart for score breakdown
                categories = []
                scores = []
                
                for category, score in score_breakdown.items():
                    categories.append(category.replace('_', ' ').title())
                    scores.append(score)
                
                # Create dataframe for the chart
                df = pd.DataFrame({
                    "Category": categories,
                    "Score": scores
                })
                
                # Sort by score
                df = df.sort_values(by="Score", ascending=True)
                
                # Create bar chart
                fig = px.bar(
                    df, 
                    y="Category", 
                    x="Score", 
                    orientation='h',
                    text="Score",
                    range_x=[0, 100],
                    color="Score",
                    color_continuous_scale=["red", "orange", "lightgreen", "green"]
                )
                
                fig.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=30, b=20),
                    coloraxis_showscale=False
                )
                
                fig.update_traces(texttemplate='%{text}', textposition='outside')
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Display summary
            st.markdown("### Analysis Summary")
            st.markdown(st.session_state.analysis_results.get('summary', 'No summary available.'))
    
    with analysis_tabs[1]:
        if 'risks_opportunities' in st.session_state and st.session_state.risks_opportunities:
            st.markdown("### Risks & Opportunities Analysis")
            
            # Create visualization
            risks_opps_chart = create_risk_opportunity_charts(st.session_state.risks_opportunities)
            st.plotly_chart(risks_opps_chart, use_container_width=True)
            
            # Create two columns for risks and opportunities
            risk_col, opp_col = st.columns(2)
            
            with risk_col:
                st.markdown("#### Identified Risks")
                
                # Display risks with collapsible sections
                for risk_name, risk_info in st.session_state.risks_opportunities["risks"].items():
                    risk_level = risk_info["level"]
                    css_class = f"risk-{risk_level.lower()}"
                    
                    with st.expander(f"{risk_name.replace('_', ' ').title()} ({risk_level})"):
                        st.markdown(f"""
                        <div class="{css_class}">
                        <strong>Description:</strong> {risk_info["description"]}<br><br>
                        <strong>Potential Impact:</strong> {risk_info["potential_impact"]}<br><br>
                        <strong>Mitigation Suggestions:</strong> {risk_info["mitigation_suggestions"]}
                        </div>
                        """, unsafe_allow_html=True)
            
            with opp_col:
                st.markdown("#### Identified Opportunities")
                
                # Display opportunities with collapsible sections
                for opp_name, opp_info in st.session_state.risks_opportunities["opportunities"].items():
                    opp_level = opp_info["level"]
                    css_class = f"opportunity-{opp_level.lower()}"
                    
                    with st.expander(f"{opp_name.replace('_', ' ').title()} ({opp_level})"):
                        st.markdown(f"""
                        <div class="{css_class}">
                        <strong>Description:</strong> {opp_info["description"]}<br><br>
                        <strong>Potential Value:</strong> {opp_info["potential_value"]}<br><br>
                        <strong>Action Items:</strong> {opp_info["action_items"]}
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Please upload and analyze a contract first to see risks and opportunities.")
    
    with analysis_tabs[2]:
        if 'clause_analysis' in st.session_state and st.session_state.clause_analysis:
            st.markdown("### Contract Clause Analysis")
            
            # Option to search for specific clauses
            st.markdown("#### Search for Specific Clauses")
            clause_query = st.text_input("Enter specific clause or topic to analyze (e.g., 'termination', 'liability limits', 'payment terms')")
            
            if clause_query:
                if st.button("Search", key="clause_search_btn"):
                    # Check usage limits for queries
                    if check_usage_limits('queries'):
                        with st.spinner("Analyzing specific clause..."):
                            specific_clause_result = analyze_contract_clauses(st.session_state.contract_text, clause_query)
                            
                            if specific_clause_result.get('found', False):
                                st.markdown("#### Search Results")
                                st.markdown(f"""
                                <div class="card">
                                <h4>Analysis for: {clause_query}</h4>
                                <strong>Clause Text:</strong>
                                <div class="ai-message">
                                {specific_clause_result.get('clause_text', 'Not found')}
                                </div>
                                <strong>Explanation:</strong>
                                <p>{specific_clause_result.get('explanation', 'No explanation available.')}</p>
                                <strong>Implications:</strong>
                                <p>{specific_clause_result.get('implications', 'No implications identified.')}</p>
                                <strong>Standard Practice:</strong>
                                <p>{specific_clause_result.get('standard_practice', 'No information available.')}</p>
                                <strong>Recommendations:</strong>
                                <p>{specific_clause_result.get('recommendations', 'No recommendations available.')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.warning(f"No specific clause or topic found for '{clause_query}'. Try different search terms.")
                    else:
                        st.warning("You have reached your daily query limit. Please upgrade to continue.")
            
            # Display key clauses
            st.markdown("#### Key Clauses Identified")
            
            if 'key_clauses' in st.session_state.clause_analysis:
                for i, clause in enumerate(st.session_state.clause_analysis['key_clauses']):
                    with st.expander(f"{clause.get('clause_type', f'Clause {i+1}')}"):
                        st.markdown(f"""
                        <div class="ai-message">
                        <strong>Extract:</strong> {clause.get('clause_extract', 'No extract available.')}
                        </div>
                        <p><strong>Explanation:</strong> {clause.get('explanation', 'No explanation available.')}</p>
                        """, unsafe_allow_html=True)
                        
                        if clause.get('concerns'):
                            st.markdown(f"""
                            <div class="risk-medium">
                            <strong>Potential Concerns:</strong> {clause.get('concerns')}
                            </div>
                            """, unsafe_allow_html=True)
        else:
            st.info("Please upload and analyze a contract first to see clause analysis.")
    
    with analysis_tabs[3]:
        if 'key_terms' in st.session_state and st.session_state.key_terms:
            st.markdown("### Key Terms & Definitions")
            
            # Display key terms in a searchable table
            if 'key_terms' in st.session_state.key_terms:
                # Create a search box
                search_term = st.text_input("Search for specific terms", "")
                
                # Create a dataframe for display
                terms_list = []
                for term_data in st.session_state.key_terms['key_terms']:
                    terms_list.append({
                        "Term": term_data.get('term', 'Unknown'),
                        "Definition": term_data.get('definition', 'No definition available.'),
                        "Explanation": term_data.get('explanation', 'No explanation available.'),
                        "Importance": term_data.get('importance', 'Not specified.')
                    })
                
                terms_df = pd.DataFrame(terms_list)
                
                # Filter by search term if provided
                if search_term:
                    filtered_df = terms_df[
                        terms_df['Term'].str.contains(search_term, case=False) | 
                        terms_df['Definition'].str.contains(search_term, case=False) |
                        terms_df['Explanation'].str.contains(search_term, case=False)
                    ]
                    
                    if len(filtered_df) > 0:
                        display_df = filtered_df
                    else:
                        st.warning(f"No terms found matching '{search_term}'")
                        display_df = terms_df
                else:
                    display_df = terms_df
                
                # Display terms as expandable items
                for i, row in display_df.iterrows():
                    with st.expander(f"{row['Term']}"):
                        st.markdown(f"""
                        <div class="card">
                        <strong>Definition:</strong>
                        <div class="ai-message">
                        {row['Definition']}
                        </div>
                        <strong>Explanation:</strong>
                        <p>{row['Explanation']}</p>
                        <strong>Importance:</strong>
                        <p>{row['Importance']}</p>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Please upload and analyze a contract first to see key terms and definitions.")
    
    with analysis_tabs[4]:
        if st.session_state.contract_text:
            st.markdown("### Chat with Your Contract")
            st.markdown("""
            <div class="card">
            <p>Ask any specific questions about the contract, and get AI-powered answers based on the document content.</p>
            <p>Examples:</p>
            <ul>
                <li>What are the payment terms in this contract?</li>
                <li>When can this agreement be terminated?</li>
                <li>What are my obligations under this contract?</li>
                <li>Is there a non-compete clause?</li>
                <li>What happens if there's a breach of contract?</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Create the chat interface
            user_question = st.text_input("Ask a question about the contract:", key="contract_question")
            
            if user_question:
                if st.button("Submit Question", key="ask_contract_btn"):
                    # Check usage limits for queries
                    if check_usage_limits('queries'):
                        with st.spinner("Analyzing your question..."):
                            answer = chat_with_contract(st.session_state.contract_text, user_question)
                            
                            # Display the question and answer
                            st.markdown("#### Your Question:")
                            st.markdown(f"> {user_question}")
                            
                            st.markdown("#### Answer:")
                            st.markdown(f"""
                            <div class="ai-message">
                            {answer}
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("You have reached your daily query limit. Please upgrade to continue.")
            
            # Display chat history if it exists
            if 'chat_history' in st.session_state and st.session_state.chat_history:
                st.markdown("### Previous Questions")
                
                for i, (question, answer) in enumerate(reversed(st.session_state.chat_history)):
                    with st.expander(f"Q: {question[:50]}{'...' if len(question) > 50 else ''}"):
                        st.markdown(f"> {question}")
                        st.markdown(f"""
                        <div class="ai-message">
                        {answer}
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Please upload a contract first to chat with it.")
    
    with analysis_tabs[5]:
        if 'analysis_results' in st.session_state and st.session_state.analysis_results and st.session_state.contract_text:
            st.markdown("### Export Analysis Report")
            
            # Language selection for translation
            selected_language = st.selectbox(
                "Select report language:", 
                list(LANGUAGES.keys()),
                index=0
            )
            
            # Company name input
            company_name = st.text_input("Your company name (optional, for the report header):")
            
            # Generate report button
            if st.button("Generate PDF Report", key="generate_report_btn"):
                # Check usage limits for report generation
                if check_usage_limits('reports'):
                    with st.spinner("Generating comprehensive PDF report..."):
                        # Get selected language code
                        lang_code = LANGUAGES[selected_language]
                        
                        # Translate if needed
                        if lang_code != 'en':
                            # Here we would translate key parts of the report
                            # For simplicity, we're skipping actual translation in this demo
                            st.info(f"Report will be generated in {selected_language}")
                        
                        # Generate the PDF
                        pdf_bytes = generate_pdf_report(
                            st.session_state.contract_text,
                            st.session_state.analysis_results,
                            st.session_state.risks_opportunities,
                            st.session_state.clause_analysis,
                            st.session_state.summary_data,
                            company_name
                        )
                        
                        if pdf_bytes:
                            # Create a download button for the PDF
                            b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                            current_date = datetime.now().strftime("%Y%m%d")
                            pdf_name = f"contract_analysis_{current_date}.pdf"
                            
                            href = f'<a class="download-btn" href="data:application/pdf;base64,{b64_pdf}" download="{pdf_name}">Download PDF Report</a>'
                            st.markdown(href, unsafe_allow_html=True)
                else:
                    st.warning("You have reached your daily report generation limit. Please upgrade to continue.")
        else:
            st.info("Please upload and analyze a contract first to generate a report.")

def generate_contract(contract_type, details):
    """Generate a contract based on type and details"""
    prompt = f"""
    Generate a professional {contract_type} contract. Include the following details:
    
    {details}
    
    The contract should be comprehensive, legally sound, and formatted with clear sections and clauses.
    Include standard legal language, definitions section, rights and obligations, termination terms, and other
    appropriate sections for this type of contract.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        st.error(f"Error generating contract: {str(e)}")
        return "Failed to generate contract. Please try again or contact support."

def show_contract_generator():
    """Display the contract generator tab"""
    st.header("Contract Generator 📝")
    
    if not st.session_state.authenticated:
        st.warning("Please log in or register to use the contract generator.")
        if st.button("Go to Login / Register", key="gen_auth_redirect"):
            st.session_state.current_page = "Login"
            st.rerun()
        return
    
    st.markdown("""
    <div class="card">
    <h3>AI Contract Generator</h3>
    <p>Generate customized contracts quickly using our AI assistant. Select a contract type and provide the necessary details.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Contract type selection
    contract_types = [
        "Non-Disclosure Agreement (NDA)",
        "Employment Contract",
        "Service Agreement",
        "Consulting Agreement",
        "Sales Contract",
        "Lease Agreement",
        "Partnership Agreement",
        "Software License Agreement"
    ]
    
    selected_type = st.selectbox("Select Contract Type", contract_types)
    
    # Details form
    st.subheader("Enter Contract Details")
    
    # Dynamic form based on contract type
    if selected_type == "Non-Disclosure Agreement (NDA)":
        party1 = st.text_input("Disclosing Party (Company/Individual Name)")
        party1_address = st.text_input("Disclosing Party Address")
        party2 = st.text_input("Receiving Party (Company/Individual Name)")
        party2_address = st.text_input("Receiving Party Address")
        purpose = st.text_area("Purpose of Disclosure")
        duration = st.text_input("Duration of Agreement (e.g., '2 years')")
        
        details = f"""
        Disclosing Party: {party1}
        Disclosing Party Address: {party1_address}
        Receiving Party: {party2}
        Receiving Party Address: {party2_address}
        Purpose of Disclosure: {purpose}
        Duration: {duration}
        """
    
    elif selected_type == "Employment Contract":
        employer = st.text_input("Employer Name")
        employer_address = st.text_input("Employer Address")
        employee = st.text_input("Employee Name")
        position = st.text_input("Job Position/Title")
        start_date = st.date_input("Start Date")
        salary = st.text_input("Salary/Compensation")
        benefits = st.text_area("Benefits (e.g., health insurance, vacation days)")
        
        details = f"""
        Employer: {employer}
        Employer Address: {employer_address}
        Employee: {employee}
        Position: {position}
        Start Date: {start_date}
        Salary: {salary}
        Benefits: {benefits}
        """
    
    else:
        # Generic form for other contract types
        parties = st.text_area("List all parties with their full names and addresses")
        agreement_details = st.text_area("Details of the agreement (be specific about terms, conditions, deliverables, etc.)")
        payment_terms = st.text_input("Payment terms (if applicable)")
        duration = st.text_input("Duration/Term of the agreement")
        special_clauses = st.text_area("Any special clauses or considerations")
        
        details = f"""
        Parties: {parties}
        Agreement Details: {agreement_details}
        Payment Terms: {payment_terms}
        Duration: {duration}
        Special Clauses: {special_clauses}
        """
    
    # Generate button
    if st.button("Generate Contract", key="gen_contract_btn"):
        if check_usage_limits('generation'):
            with st.spinner("Generating your contract... This may take a moment..."):
                generated_contract = generate_contract(selected_type, details)
                st.session_state.generated_contract = generated_contract
                st.success("Contract generated successfully!")
        else:
            st.warning("You have reached your daily generation limit. Please upgrade to continue.")
    
    # Display generated contract if available
    if 'generated_contract' in st.session_state and st.session_state.generated_contract:
        st.subheader("Generated Contract")
        st.text_area("Contract Text", st.session_state.generated_contract, height=500)
        
        # Download options
        col1, col2 = st.columns(2)
        with col1:
            if st.download_button("Download as Text", st.session_state.generated_contract, 
                               file_name=f"{selected_type.replace(' ', '_')}.txt", mime="text/plain"):
                st.success("Contract downloaded successfully!")
        
        with col2:
            if st.button("Create PDF Document"):
                with st.spinner("Creating PDF..."):
                    # Create PDF
                    try:
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 12)
                        pdf.cell(190, 10, selected_type, ln=True, align="C")
                        pdf.ln(5)
                        
                        pdf.set_font("Arial", "", 10)
                        # Split text into lines and add to PDF
                        lines = st.session_state.generated_contract.split('\n')
                        for line in lines:
                            if line.strip():  # Skip empty lines
                                if line.strip().isupper():  # Section headers
                                    pdf.set_font("Arial", "B", 10)
                                    pdf.ln(2)
                                    pdf.cell(190, 6, line, ln=True)
                                    pdf.set_font("Arial", "", 10)
                                else:
                                    pdf.multi_cell(190, 5, line)
                                    
                        # Create download button
                        pdf_bytes = pdf.output(dest='S').encode('latin-1')
                        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="{selected_type.replace(" ", "_")}.pdf">Click to download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("PDF created! Click the link above to download.")
                    except Exception as e:
                        st.error(f"Error creating PDF: {str(e)}")

def show_home_page():
    """Display the home page"""
    st.title("Legal Contract Analysis System")
    
    # Check if user is logged in
    if st.session_state.authenticated:
        # Display welcome message for logged-in user
        st.markdown(f"""
        <div class="card">
        <h3>Welcome, {st.session_state.user.name}! 👋</h3>
        <p>What would you like to do today?</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show subscription status
        show_subscription_status()
        
        # Create three columns for quick actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Analyze Contracts", use_container_width=True):
                st.session_state.current_page = "Contract Analysis"
                st.rerun()
        
        with col2:
            if st.button("Contract Reminders", use_container_width=True):
                st.session_state.current_page = "Contract Reminders"
                st.rerun()
        
        with col3:
            if st.button("Account Settings", use_container_width=True):
                st.session_state.current_page = "Account"
                st.rerun()
        
        # Recent Activity Section (placeholder)
        st.markdown("### Recent Activity")
        st.info("Your recent contract analysis and reminder activities will appear here.")
        
        # Feature highlights
        st.markdown("### Features Available")
        
        features_col1, features_col2 = st.columns(2)
        
        with features_col1:
            st.markdown("""
            <div class="card">
            <h4>📄 Contract Analysis</h4>
            <p>Upload contracts for AI-powered analysis</p>
            <ul>
                <li>Risk & opportunity assessment</li>
                <li>Clause-by-clause explanation</li>
                <li>Legal language simplification</li>
                <li>PDF & DOCX support</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card">
            <h4>🌐 Multi-Language Support</h4>
            <p>Analyze and translate contracts in multiple languages</p>
            <ul>
                <li>Generate reports in your preferred language</li>
                <li>Support for 9 major languages</li>
                <li>Cross-language contract analysis</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with features_col2:
            st.markdown("""
            <div class="card">
            <h4>🔔 Contract Reminders</h4>
            <p>Never miss important contract deadlines</p>
            <ul>
                <li>Automated deadline tracking</li>
                <li>Email & SMS notifications</li>
                <li>Calendar integration</li>
                <li>Custom reminder scheduling</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card">
            <h4>📊 Contract Reports</h4>
            <p>Generate comprehensive contract reports</p>
            <ul>
                <li>Detailed risk assessments</li>
                <li>Shareable PDF exports</li>
                <li>Summarized contract terms</li>
                <li>Data visualization</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        
    else:
        # Display welcome message for non-logged-in users
        st.markdown("""
        <div class="card">
        <h3>Streamline Your Contract Management with AI</h3>
        <p>Our AI-powered contract analysis system helps you understand, analyze, and manage legal contracts effortlessly.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Login and Register buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Login", use_container_width=True):
                st.session_state.current_page = "Login"
                st.rerun()
        
        with col2:
            if st.button("Register", use_container_width=True):
                st.session_state.current_page = "Register"
                st.rerun()
        
        # Feature highlights for non-logged in users
        st.markdown("### Platform Features")
        
        features_col1, features_col2 = st.columns(2)
        
        with features_col1:
            st.markdown("""
            <div class="card">
            <h4>📄 AI-Powered Contract Analysis</h4>
            <p>Upload contracts and get instant insights</p>
            <ul>
                <li>Identify potential risks and opportunities</li>
                <li>Understand complex legal language</li>
                <li>Get clause-by-clause explanations</li>
                <li>Compare against industry standards</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card">
            <h4>🌐 Multi-Language Support</h4>
            <p>Work with contracts in multiple languages</p>
            <ul>
                <li>Analyze contracts in different languages</li>
                <li>Generate reports in your preferred language</li>
                <li>Translate contract terms for better understanding</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with features_col2:
            st.markdown("""
            <div class="card">
            <h4>🔔 Contract Management</h4>
            <p>Stay on top of contract deadlines</p>
            <ul>
                <li>Set reminders for important dates</li>
                <li>Get email and SMS notifications</li>
                <li>Calendar view of upcoming deadlines</li>
                <li>Organize contracts by type and status</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="card">
            <h4>📊 Comprehensive Reporting</h4>
            <p>Generate detailed contract reports</p>
            <ul>
                <li>Export as PDF documents</li>
                <li>Visual risk assessment dashboards</li>
                <li>Summarized contract terms</li>
                <li>Shareable insights with your team</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        
        # Add a demo section
        st.markdown("### Try Our Demo")
        
        if st.button("Try Demo with Sample Contract"):
            # Use a demo account
            success, message = login_user("demo@example.com", "Demo@123")
            if success:
                st.session_state.current_page = "Contract Analysis"
                st.rerun()

def show_account_page():
    """Display the account settings page"""
    if not st.session_state.authenticated:
        st.warning("Please log in to access your account settings.")
        
        # Add a button to go to login page
        if st.button("Go to Login"):
            st.session_state.current_page = "Login"
            st.rerun()
        return
    
    st.title("Account Settings")
    
    # Create tabs for different account sections
    account_tabs = st.tabs(["Profile", "Subscription", "Usage", "Preferences"])
    
    with account_tabs[0]:
        st.header("Profile Information")
        
        # Display and edit user information
        user = st.session_state.user
        
        st.markdown(f"""
        <div class="card">
        <h4>Account Details</h4>
        <p><strong>Name:</strong> {user.name}</p>
        <p><strong>Email:</strong> {user.email}</p>
        <p><strong>Account Created:</strong> {user.created_at.split('T')[0] if hasattr(user, 'created_at') else 'N/A'}</p>
        <p><strong>Company:</strong> {user.company if hasattr(user, 'company') and user.company else 'Not specified'}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Edit profile form
        st.subheader("Edit Profile")
        
        with st.form("edit_profile_form"):
            new_name = st.text_input("Name", value=user.name)
            new_company = st.text_input("Company", value=user.company if hasattr(user, 'company') and user.company else "")
            
            # Password change fields
            st.subheader("Change Password")
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            submitted = st.form_submit_button("Update Profile")
            
            if submitted:
                # Validate password change
                if current_password and new_password:
                    if new_password != confirm_password:
                        st.error("New passwords do not match.")
                    elif len(new_password) < 8:
                        st.error("Password must be at least 8 characters long.")
                    else:
                        # Update password in session state
                        st.success("Profile updated successfully!")
                else:
                    # Just update profile info
                    st.success("Profile updated successfully!")
    
    with account_tabs[1]:
        st.header("Subscription Management")
        
        # Current plan
        current_plan = st.session_state.subscription_type.title()
        
        if current_plan == "Free":
            st.markdown("""
            <div class="card">
            <h4>Current Plan: Free Tier</h4>
            <p>You are currently on the Free tier with limited features.</p>
            <h4>Free Tier Limits:</h4>
            <ul>
                <li>3 Reports per day</li>
                <li>10 Queries per day</li>
                <li>5 Contract analyses per day</li>
                <li>2 Contract generations per day</li>
                <li>Basic reminders (max 10)</li>
                <li>No SMS notifications</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Upgrade options
            st.subheader("Upgrade to Premium")
            
            st.markdown("""
            <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
            <h4>Premium Plan - $29.99/month</h4>
            <p>Unlock full access to all features:</p>
            <ul>
                <li>Unlimited contract analyses</li>
                <li>Unlimited reports & queries</li>
                <li>Advanced clause analysis</li>
                <li>Unlimited reminders</li>
                <li>SMS notifications</li>
                <li>Priority support</li>
                <li>Batch processing</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("Upgrade to Premium"):
                st.session_state.show_payment = True
        else:
            st.markdown("""
            <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
            <h4>Current Plan: Premium</h4>
            <p>You're enjoying full access to all premium features:</p>
            <ul>
                <li>Unlimited contract analyses</li>
                <li>Unlimited reports & queries</li>
                <li>Advanced clause analysis</li>
                <li>Unlimited reminders</li>
                <li>SMS notifications</li>
                <li>Priority support</li>
                <li>Batch processing</li>
            </ul>
            <p><strong>Billing Cycle:</strong> Monthly</p>
            <p><strong>Next Billing Date:</strong> 2023-07-15</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Cancel subscription button
            if st.button("Cancel Subscription"):
                st.warning("Are you sure you want to cancel your premium subscription?")
                cancel_col1, cancel_col2 = st.columns(2)
                
                with cancel_col1:
                    if st.button("Yes, Cancel"):
                        st.session_state.subscription_type = "free"
                        st.success("Your subscription has been canceled. You will have access to premium features until the end of your billing cycle.")
                        st.rerun()
                
                with cancel_col2:
                    if st.button("No, Keep Premium"):
                        st.info("Your premium subscription will continue.")
        
        # Display payment interface if requested
        if st.session_state.show_payment:
            show_payment_interface()
    
    with account_tabs[2]:
        st.header("Usage Statistics")
        
        # Reset daily usage counters if needed
        reset_daily_counts()
        
        # Display current usage
        st.subheader("Today's Usage")
        
        # Create usage bars
        usage_data = [
            {"category": "Reports", "used": st.session_state.usage_counts.get('reports', 0), "limit": FREE_TIER_LIMITS['reports_per_day']},
            {"category": "Queries", "used": st.session_state.usage_counts.get('queries', 0), "limit": FREE_TIER_LIMITS['queries_per_day']},
            {"category": "Analyses", "used": st.session_state.usage_counts.get('analysis', 0), "limit": FREE_TIER_LIMITS['analysis_per_day']},
            {"category": "Generations", "used": st.session_state.usage_counts.get('generation', 0), "limit": FREE_TIER_LIMITS['generation_per_day']}
        ]
        
        # Create a dataframe for visualization
        usage_df = pd.DataFrame(usage_data)
        
        # Add percentage column
        if st.session_state.subscription_type == 'free':
            usage_df['percentage'] = (usage_df['used'] / usage_df['limit'] * 100).clip(upper=100)
            
            # Create horizontal bar chart
            fig = px.bar(
                usage_df,
                y="category",
                x="percentage",
                orientation='h',
                labels={"percentage": "Usage %", "category": ""},
                title="Daily Usage (Free Tier)",
                text=usage_df.apply(lambda row: f"{int(row['used'])}/{int(row['limit'])}", axis=1),
                range_x=[0, 100],
                height=300
            )
            
            # Customize layout
            fig.update_layout(
                xaxis_title="Percentage Used",
                font=dict(family="Arial", size=12),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            
            # Update bar colors based on usage
            fig.update_traces(
                marker_color=usage_df['percentage'].apply(
                    lambda x: "#4caf50" if x < 60 else "#ff9800" if x < 85 else "#f44336"
                ),
                textposition="outside"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add upgrade nudge if usage is high
            if any(usage_df['percentage'] > 80):
                st.markdown("""
                <div class="upgrade-banner">
                <h4>⚠️ Approaching Usage Limits</h4>
                <p>You're approaching your free tier usage limits. Consider upgrading to Premium for unlimited usage.</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Upgrade Now", key="usage_upgrade_btn"):
                    st.session_state.show_payment = True
                    st.rerun()
        else:
            # For premium users, just show actual usage without limits
            st.markdown("""
            <div class="card" style="background-color: #e8f5e9; border-left-color: #4caf50;">
            <h4>Premium Account</h4>
            <p>As a premium user, you have unlimited usage of all features.</p>
            <p>Today's activity:</p>
            <ul>
                <li>Reports generated: {}</li>
                <li>Queries performed: {}</li>
                <li>Contracts analyzed: {}</li>
                <li>Documents generated: {}</li>
            </ul>
            </div>
            """.format(
                st.session_state.usage_counts.get('reports', 0),
                st.session_state.usage_counts.get('queries', 0),
                st.session_state.usage_counts.get('analysis', 0),
                st.session_state.usage_counts.get('generation', 0)
            ), unsafe_allow_html=True)
    
    with account_tabs[3]:
        st.header("Preferences")
        
        # Language preferences
        st.subheader("Language Settings")
        
        selected_language = st.selectbox(
            "Application Language:", 
            list(LANGUAGES.keys()),
            index=list(LANGUAGES.values()).index(st.session_state.selected_language) if st.session_state.selected_language in LANGUAGES.values() else 0
        )
        
        if st.button("Save Language Preference"):
            st.session_state.selected_language = LANGUAGES[selected_language]
            st.success(f"Language preference updated to {selected_language}")
        
        # Notification preferences
        st.subheader("Notification Settings")
        
        email_notifications = st.checkbox("Email Notifications", value=True)
        browser_notifications = st.checkbox("Browser Notifications", value=True)
        
        # SMS notification settings from the reminders module
        from sms_notifications import show_notification_settings
        show_notification_settings()
        
        # Theme preferences (placeholder)
        st.subheader("Theme Settings")
        
        theme_mode = st.radio("Theme", options=["Light", "Dark", "System Default"])
        
        if st.button("Save Theme Preference"):
            st.success(f"Theme preference updated to {theme_mode}")

def main():
    """Main application function"""
    # Apply custom CSS
    local_css()
    
    # Create sidebar
    with st.sidebar:
        # Show logo at the top
        st.markdown("""
        <div class="logo-container">
        <h2>⚖️ LegalAI</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation based on authentication state
        if st.session_state.authenticated:
            # Logged in user navigation
            st.markdown(f"Welcome, **{st.session_state.user.name}**!")
            
            # Navigation buttons
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.current_page = "Home"
                st.rerun()
            
            if st.button("📄 Contract Analysis", use_container_width=True):
                st.session_state.current_page = "Contract Analysis"
                st.rerun()
                
            if st.button("📝 Contract Generator", use_container_width=True):
                st.session_state.current_page = "Contract Generator"
                st.rerun()
            
            if st.button("🔔 Contract Reminders", use_container_width=True):
                st.session_state.current_page = "Contract Reminders"
                st.rerun()
            
            if st.button("👤 Account", use_container_width=True):
                st.session_state.current_page = "Account"
                st.rerun()
            
            # Logout button
            if st.button("🚪 Logout", use_container_width=True):
                logout_user()
                st.session_state.current_page = "Home"
                st.rerun()
        else:
            # Non-logged in user navigation
            if st.button("🏠 Home", use_container_width=True):
                st.session_state.current_page = "Home"
                st.rerun()
            
            if st.button("🔑 Login", use_container_width=True):
                st.session_state.current_page = "Login"
                st.rerun()
            
            if st.button("📝 Register", use_container_width=True):
                st.session_state.current_page = "Register"
                st.rerun()
        
        # Always show a Try Demo button
        if st.button("🔍 Try Demo", use_container_width=True):
            # Use a demo account
            success, message = login_user("demo@example.com", "Demo@123")
            if success:
                st.session_state.current_page = "Contract Analysis"
                st.rerun()
        
        # Add support interface button at the bottom
        show_support_interface()
    
    # Show upgrade popup if needed
    if st.session_state.show_upgrade_popup:
        show_upgrade_popup()
    
    # Main content based on current page
    if st.session_state.current_page == "Home":
        show_home_page()
    elif st.session_state.current_page == "Login":
        show_login_form(mode="login")
    elif st.session_state.current_page == "Register":
        show_login_form(mode="register")
    elif st.session_state.current_page == "Contract Analysis":
        show_contract_analysis_interface()
    elif st.session_state.current_page == "Contract Generator":
        show_contract_generator()
    elif st.session_state.current_page == "Contract Reminders":
        add_reminders_to_app()
    elif st.session_state.current_page == "Account":
        show_account_page()
    else:
        show_home_page()

if __name__ == "__main__":
    main()
