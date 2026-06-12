# Overall goal
Create a platform for collecting all public statements made by politicians in the Danish Parliament.
This would require me to know the members of the parliament and made able to link public statements to those people.

# Scraping
* Scrape a bunch of news articles from trusted, public, Danish sources
* Fetch data about proposed legislation and voting of each politician from the "Folketinget" website

# Processing
* Filter paragraphs/sentences that are linked to certain politicians
* Create database
  * DimPoliticians
  * DimParties
  * DimNewsSources
  * FactPoliticianStatus
  * FactStatements
  * FactLegislation
  
# Website
* Display overview of each politician in terms of statements and legislation voting over time