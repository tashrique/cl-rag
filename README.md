# College Application RAG Agents


![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)

![Built with Love for Flare](https://img.shields.io/badge/built%20with%20%E2%9D%A4%EF%B8%8F%20for-Flare-orange)


A suite of specialized Retrieval-Augmented Generation (RAG) agents designed to assist college applicants with different information needs. Each agent is optimized for specific use cases, from quick fact lookups to comprehensive research and news gathering.

## RAG Agents Overview

This project includes three specialized RAG agents, each with a unique design philosophy and purpose:

### 1. Fast-RAG: Rapid Facts and Direct Answers

**Purpose**: Delivers concise, data-focused responses for quick lookups and specific queries.

**Technical Implementation**:
- **Prompt Engineering**: Optimized for brevity and factual precision with minimal explanatory text
- **Data Sources**: Primarily Common Data Sets (CDS) and official university statistics
- **Response Style**: Bullet points, direct statements, and clear data presentation
- **Architecture**: Streamlined retrieval pipeline with minimal post-processing to maximize speed

**Ideal Use Cases**:
- Checking specific admission rates, test score ranges, or deadlines
- Quick verification of application requirements
- Direct statistical comparisons between institutions

### 2. Deep-Search RAG: Comprehensive Analysis

**Purpose**: Provides in-depth, nuanced responses for complex questions requiring thorough exploration.

**Technical Implementation**:
- **Prompt Engineering**: Structured for comprehensive coverage with clear organization and multi-faceted analysis
- **Data Sources**: Common Data Sets, institutional research, academic publications, and educational resources
- **Response Style**: Well-structured with headings, detailed explanations, and contextual information
- **Architecture**: Multi-step retrieval with knowledge integration and reasoning

**Ideal Use Cases**:
- Understanding complex admissions strategies
- Detailed scholarship application guidance
- Multi-faceted college comparison requests
- In-depth program evaluation questions

### 3. Community-Search RAG: News and Social Insights

**Purpose**: Aggregates and synthesizes news, social media discussions, and community insights about colleges.

**Technical Implementation**:
- **Prompt Engineering**: Designed with journalistic framing to present trends, discussions, and timely updates
- **Data Sources**: Reddit discussions, news articles, university announcements, and social media trends
- **Response Style**: News-style presentation with headlines, key points, and source attribution
- **Architecture**: Multi-source retrieval with recency prioritization and source diversity management

**Ideal Use Cases**:
- Understanding current applicant experiences and concerns
- Tracking recent changes to admissions policies
- Following discussions about specific programs or institutions
- Getting insights about campus life and student experiences

## Technical Architecture

All three RAG agents share a common architectural framework while implementing specialized components:

### Core Components

1. **Router**: Analyzes user queries and directs them to appropriate processing pipelines
   - Uses the Gemini model for intent classification
   - Routes based on query complexity, information need, and required response type

2. **Retriever**: Searches for and retrieves relevant information from vector databases
   - Implements semantic search with Pinecone vector database
   - Uses embedding models to convert queries into vector representations
   - Retrieves context documents based on semantic similarity

3. **Responder**: Generates tailored responses based on retrieved context and specialized prompts
   - Uses the Gemini model with custom system prompts for each agent type
   - Implements HTML source linking for attribution and fact verification
   - Customized response formats based on agent specialization

### Data Pipeline

The project includes a sophisticated data processing pipeline:

1. **Data Collection**: 
   - Scraped data from Common Data Sets (CDS) for universities
   - Gathered Reddit discussions from r/ApplyingToCollege and other relevant subreddits
   - Collected news articles and university announcements

2. **Data Cleaning**:
   - Normalized university names and attribute formats
   - Structured data into a consistent schema
   - Merged multiple data sources with deduplication

3. **Vector Database Creation**:
   - Chunked text into appropriate semantic units
   - Generated embeddings using state-of-the-art embedding models
   - Stored in Pinecone with appropriate metadata

## Prompt Engineering

Each RAG agent features carefully engineered prompts optimized for their specific purpose:

### Fast-RAG Prompts

Designed for brevity and precision:
- Clear instructions to prioritize facts over explanations
- Examples of concise data presentation formats
- Strict guidance on source attribution with minimal surrounding text

### Deep-Search RAG Prompts

Structured for comprehensive coverage:
- Detailed organization templates for complex responses
- Instructions for seamless integration of multiple information sources
- Guidance on providing actionable insights and strategies

### Community-Search RAG Prompts

Crafted for news-style information presentation:
- Journalistic framing with headlines and key points
- Direction on balancing official sources with community perspectives
- Guidelines for presenting trending topics and time-sensitive information

## Data Sources

The RAG agents utilize a diverse set of data sources:

1. **Common Data Sets (CDS)**:
   - Standardized institutional data from universities
   - Includes admission statistics, enrollment figures, and academic profiles
   - Scraped from university websites and processed for consistency

2. **Reddit and Social Media**:
   - Discussions from r/ApplyingToCollege, r/CollegeAdmissions, etc.
   - Student experiences and insights from recent application cycles
   - Anonymized and filtered for appropriateness

3. **News and Announcements**:
   - Recent policy changes and institutional updates
   - Scholarship and financial aid news
   - Educational policy developments

## API and Integration

The RAG agents are implemented as API services:
- FastAPI-based endpoints for query processing
- Docker containerization for easy deployment
- Configurable retrieval parameters for different use cases
- CORS support for web client integration

## Getting Started

### Prerequisites
- Python 3.10+
- Pinecone account
- Google API key for Gemini models

### Installation

```bash
# Clone the repository
git clone [repository-url]

# Navigate to the desired agent directory
cd [fast-rag|deep-search-rag|community-search-rag]

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and configuration

# Start the service
./start.sh
```

## Usage Examples

### Fast-RAG

```
Query: "What is UCLA's acceptance rate?"
Response: 
- UCLA's overall acceptance rate is <a href="source:UCLA_CDS_2023">8.6%</a> for the 2023-2024 academic year
- For California residents: <a href="source:UCLA_Admissions">10.8%</a>
- For out-of-state applicants: <a href="source:UCLA_Admissions">7.2%</a>
```

### Deep-Search RAG

```
Query: "How should I approach applying to highly selective schools?"

Response: [Comprehensive multi-paragraph response with structured sections, strategic advice, and factual data points with source attribution]
```

### Community-Search RAG

```
Query: "What are students saying about UC Berkeley's application process?"

Response: [News-style summary of recent Reddit discussions, trends, and experiences with the Berkeley application process]
```

## Future Development

- Integration with personalized recommendation systems
- Expanded data sources including more international universities
- Real-time data updating from official university feeds
- Enhanced visualization capabilities for statistical data

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built for the Flare AI Hackathon
- Utilizes Google's Gemini models
- Special thanks to all the educational institutions that make their Common Data Sets publicly available 