import csv
import re
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report


def load_titles(filepath):
    """Load job titles from text file (one per line)."""
    titles = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                titles.append(line)
    return titles


def load_companies(filepath):
    """Load company names from CSV file."""
    companies = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name_latest"].strip()
            if name:
                companies.append(name)
            # Also include previous names if available
            prev = row.get("names_previous", "").strip()
            if prev:
                companies.append(prev)
    return companies


def clean_text(text):
    """Basic text cleaning."""
    text = re.sub(r"[^a-zA-Z0-9\s&/\-]", "", text)
    return text.lower().strip()


def train_and_save_model(texts, label, vectorizer_path, model_path):
    """
    Train a Naive Bayes classifier for a single entity type.
    Positive class = the entity (title or company), negative class = the other.
    """
    # This is handled in the combined training below
    pass


def main():
    print("Loading data...")
    titles = load_titles("titles_combined.txt")
    companies = load_companies("companies.csv")

    print(f"  Job titles loaded: {len(titles)}")
    print(f"  Company names loaded: {len(companies)}")

    # Clean texts
    titles_clean = [clean_text(t) for t in titles]
    companies_clean = [clean_text(c) for c in companies]

    # --- Train Job Title Classifier ---
    # Positive: job titles, Negative: company names (sampled to balance)
    print("\n--- Training Job Title Classifier ---")
    # Sample companies to roughly match title count for negative examples
    np.random.seed(42)
    neg_samples_for_titles = list(np.random.choice(
        companies_clean, size=min(len(companies_clean), len(titles_clean)), replace=False
    ))

    title_texts = titles_clean + neg_samples_for_titles
    title_labels = [1] * len(titles_clean) + [0] * len(neg_samples_for_titles)

    title_vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 5), max_features=50000
    )
    X_title = title_vectorizer.fit_transform(title_texts)

    X_train, X_test, y_train, y_test = train_test_split(
        X_title, title_labels, test_size=0.2, random_state=42, stratify=title_labels
    )

    title_model = MultinomialNB(alpha=0.1)
    title_model.fit(X_train, y_train)

    print("Job Title Classifier - Test Set Performance:")
    y_pred = title_model.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=["Not Title", "Job Title"]))

    # Save title model
    with open("title_vectorizer.pkl", "wb") as f:
        pickle.dump(title_vectorizer, f)
    with open("title_model.pkl", "wb") as f:
        pickle.dump(title_model, f)
    print("Saved: title_vectorizer.pkl, title_model.pkl")

    # --- Train Company Name Classifier ---
    print("\n--- Training Company Name Classifier ---")
    # Positive: company names, Negative: job titles (sampled to balance)
    neg_samples_for_companies = list(np.random.choice(
        titles_clean, size=min(len(titles_clean), len(companies_clean)), replace=False
    ))

    company_texts = companies_clean + neg_samples_for_companies
    company_labels = [1] * len(companies_clean) + [0] * len(neg_samples_for_companies)

    company_vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 5), max_features=50000
    )
    X_company = company_vectorizer.fit_transform(company_texts)

    X_train, X_test, y_train, y_test = train_test_split(
        X_company, company_labels, test_size=0.2, random_state=42, stratify=company_labels
    )

    company_model = MultinomialNB(alpha=0.1)
    company_model.fit(X_train, y_train)

    print("Company Name Classifier - Test Set Performance:")
    y_pred = company_model.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=["Not Company", "Company"]))

    # Save company model
    with open("company_vectorizer.pkl", "wb") as f:
        pickle.dump(company_vectorizer, f)
    with open("company_model.pkl", "wb") as f:
        pickle.dump(company_model, f)
    print("Saved: company_vectorizer.pkl, company_model.pkl")

    # --- Quick demo ---
    print("\n--- Demo Predictions ---")
    test_strings = [
        "Software Engineer",
        "Google Inc",
        "Senior Data Scientist",
        "Goldman Sachs Group",
        "Registered Nurse",
        "Pfizer Inc",
        "Chief Executive Officer",
        "Gilead Sciences",
    ]
    for s in test_strings:
        s_clean = clean_text(s)
        t_vec = title_vectorizer.transform([s_clean])
        c_vec = company_vectorizer.transform([s_clean])
        t_prob = title_model.predict_proba(t_vec)[0][1]
        c_prob = company_model.predict_proba(c_vec)[0][1]
        print(f"  '{s}' -> Title: {t_prob:.3f}, Company: {c_prob:.3f}")


if __name__ == "__main__":
    main()
