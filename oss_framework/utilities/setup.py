from setuptools import setup, find_packages

setup(
    name="oss-framework-utilities",
    version="1.0.0",
    description="Reusable utilities library for education analytics data processing",
    author="OSS Framework Team",
    author_email="oss-framework@example.com",
    url="https://github.com/yourorg/oss-framework",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pandas>=1.5.0",
        "numpy>=1.23.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
        "azure": [
            "azure-storage-blob>=12.14",
            "azure-identity>=1.12",
        ],
        "postgres": [
            "psycopg2-binary>=2.9",
            "sqlalchemy>=2.0",
        ],
        "bigquery": [
            "google-cloud-bigquery>=3.11",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Education",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
