from setuptools import setup, find_packages

setup(
    name="ebay_monitor",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'flask==3.0.0',
        'requests==2.31.0',
        'python-dotenv==1.0.0'
    ],
)