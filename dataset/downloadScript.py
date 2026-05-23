import kagglehub

# Download latest version
path = kagglehub.dataset_download("nitishabharathi/email-spam-dataset")

print("Path to dataset files:", path)