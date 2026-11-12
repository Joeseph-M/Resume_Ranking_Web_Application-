# Resume_Ranking_Web_Application
Mass hiring is a time-intensive function for Recruiters as 1000s of CVs need to be vetted, coupled with administrative overload this becomes inefficient,  this app's main goal is to ingest a folder of resumes and rank order in terms of relevance to the role, helping to focus the Recruiter's limited time to the most relevant CVs

The aim of the project is to dramaticaly shorten the Recruiter's time taken to open, read/vet, qualify candidates who apply for a job, Recruiters are currently opening applicant's resume one-by-one in the ATS which is ranked by the date of applicaiton, it's inefficient and highly dependent on the Recruiter's duration of focus while other urgent tasks takes his/her time away. 

The application extracts text from candidate resumes, compares them against a job description and generates a ranked list based on text similarity and keyword coverage.


### How to run this locally 

1. In VScode, cloe this repository from github 
2. Create a virtual environment:
    python -m venv .venv 
3. Activate the environment:
    .venv\Scripts\Activate.ps1 
4. Install dependencies:
    python -m pip install -r requirements.txt 
5. Start the application:
    python main.py 
6. Open in your browser (no internet is needed)
    http://127.0.0.1:5000 
7. Paste your job description into the box 
8. Select the folder containing your resumes (100mb limit)
9. Click Rank Resumes 
10. Resumes are now ranked based on relevance to the JD and downloadabe in a ZIP file (on desktop)


### How TF-IDF Cosine Similarity works 

There's a YT video online that explains this quite well here: https://youtu.be/x1u5TotQ0G0?si=sgv6Ok9Hc7vnL7D-

The general idea is to remove letters/words that deliver little to no meaning to the Recruiter and we extract the remaining text locally, it applies TF-IDF cosine similarity (70%) with the JD term coverage of (30%). Scores are text-based only they do not establish qualification, performance, suitability, cultural-fit, in other words this is NOT a replacement for the Recruiter's human judgement, it simply pair's an applicant's Resume to the JD and ranks it in terms of relevance.
Everything is done locally there's no AI or internet needed to run this so Resumes are safe within the company's / Recruiter's control. 


## Demonstration of the project 

![Resume Ranking Application](Home_Page.jpg)













