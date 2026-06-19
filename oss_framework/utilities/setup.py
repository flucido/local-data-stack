from setuptools import find_packages, setup

setup(
    name="oss-framework-utilities",
    version="1.0.0",
    description="Reusable utilities library for education analytics data processing",
    author="OSS Framework Team",
    author_email="oss-framework@example.com",
    url="https://github.com/yourorg/oss-framework",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.12",
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
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Education",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
