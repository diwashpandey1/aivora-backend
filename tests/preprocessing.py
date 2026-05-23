import pandas as pd
import re
import nltk

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

# Download NLTK resources
nltk.download('stopwords')
nltk.download('punkt')

# Load dataset
df = pd.read_csv(
    "dataset/sms_spam/spam.csv",
    encoding="latin-1"
)

# Keep only useful columns
df = df[['v1', 'v2']]

# Rename columns
df.columns = ['label', 'message']

# Encode labels
# ham = 0
# spam = 1
df['label'] = df['label'].map({
    'ham': 0,
    'spam': 1
})

# Initialize tools
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))


# Preprocessing function
def preprocess_text(text):

    # 1. Convert to lowercase
    text = text.lower()

    # 2. Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)

    # 3. Remove email addresses
    text = re.sub(r'\S+@\S+', '', text)

    # 4. Remove numbers
    text = re.sub(r'\d+', '', text)

    # 5. Remove special characters
    text = re.sub(r'[^a-zA-Z\s]', '', text)

    # 6. Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # 7. Tokenization
    tokens = word_tokenize(text)

    # 8. Remove stopwords + stemming
    cleaned_tokens = []

    for word in tokens:

        if word not in stop_words:
            stemmed_word = stemmer.stem(word)
            cleaned_tokens.append(stemmed_word)

    # 9. Join words back
    cleaned_text = " ".join(cleaned_tokens)

    return cleaned_text


# Apply preprocessing
df['message'] = df['message'].apply(preprocess_text)

# Remove null values
df.dropna(inplace=True)

# Remove empty messages
df = df[df['message'].str.strip() != ""]

# Print sample
print(df.head())

# Save cleaned dataset
df.to_csv(
    "dataset/sms_spam/cleaned_sms.csv",
    index=False
)

print("\nSMS preprocessing completed successfully.")