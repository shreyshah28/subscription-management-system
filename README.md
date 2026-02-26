# 🎬 Netflix Subscription & Business Analytics System

A comprehensive full-stack application that simulates a subscription-based streaming platform. This project integrates a **Streamlit** frontend with a **PostgreSQL** relational database, featuring complex data handling, user authentication, and administrative analytics.

## 📌 Project Overview
Developed as part of the **Bachelor of Engineering in CSE (AI)** curriculum, this system focuses on the practical application of Data Structures and Database Management Systems (DBMS).



### 🛠️ Key Technical Features
* **Secure Authentication:** Implements SHA-256 password hashing for user security.
* **Relational Database Design:** A multi-table PostgreSQL schema ensuring ACID compliance and data integrity.
* **Kaggle Data Integration:** Custom ETL script to migrate 8,000+ real-world titles from the Netflix Movies and TV Shows dataset.
* **Business Intelligence Dashboard:** Real-time visualization of revenue, user growth, and content distribution using Plotly.
* **Subscription Logic:** Automated expiry tracking and transaction logging for different plan tiers.

## 🗄️ Database Architecture
The system relies on a structured relational model to manage high volumes of data efficiently:



* `users`: Core profile storage with role-based access control (Admin/User).
* `content`: Metadata for thousands of titles including genres, ratings, and release years.
* `subscriptions`: Dynamic tracking of active user plans and validity periods.
* `payments`: Financial ledger for all successful and pending transactions.
* `visitors`: Analytics table to track platform engagement.

## 📂 File Structure & Logic
* `app.py`: The UI engine built with Streamlit, handling the "Netflix Clone" dark-theme interface.
* `backend.py`: The core logic layer containing classes for User Management, Activity Tracking, and Subscription logic.
* `database.py`: Handles connection pooling and automated schema/table creation.
* `load_kaggle_content.py`: A data engineering tool to clean and import the `netflix_titles.csv` dataset.
* `seed_netflix_realistic.py`: A simulation script that generates 12 months of realistic mock data for testing analytics.

## 🚀 Getting Started

### Prerequisites
* Python 3.8+
* PostgreSQL
* Libraries: `streamlit`, `pandas`, `psycopg2`, `plotly`

### Installation
1.  **Clone the Repo:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
    cd YOUR_REPO_NAME
    ```
2.  **Setup Database:**
    Update the `DB_PASS` in `database.py` with your PostgreSQL password, then run:
    ```bash
    python database.py
    ```
3.  **Import Data:**
    ```bash
    python load_kaggle_content.py
    ```
4.  **Launch Platform:**
    ```bash
    streamlit run app.py
    ```

## 🧠 Future Roadmap (AI Integration)
As a CSE (AI) student, future iterations will include:
* **Content Recommendation:** A Machine Learning model to suggest titles based on user viewing history.
* **Churn Analytics:** Predicting user subscription cancellations using historical payment patterns.

---
**Author:** Shah Shrey Rajubhai  
**Institution:** LJ University, Ahmedabad  
**Semester:** 3rd Semester (BE CSE - AI)
