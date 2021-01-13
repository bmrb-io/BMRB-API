#!/usr/bin/env python3
# This script is used to produce XML files from entries files for a Thomson Reuters

# The contact e-mail for this project at Reuters is: megan.force@thomsonreuters.com

import logging
import os
import sys
import time
import xml.etree.cElementTree as eTree
import zipfile
from io import BytesIO
from xml.etree.ElementTree import tostring as xml_tostring

import pynmrstar
from lxml import etree

from bmrbapi.utils.connections import PostgresConnection


def xml(result_location):
    with PostgresConnection(ets=True) as c:
        c.execute("""
        SELECT bmrbnum,release_date
         FROM entrylog
         WHERE status like 'rel%' AND lit_search_required LIKE 'N'
         ORDER BY bmrbnum""")
        entry_data = c.fetchall()

    # Set up the validation code and import the schema
    schema_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "xml_generate",
                               "DRC_schema_providers.V1.xsd")
    xmlschema = etree.XMLSchema(etree.parse(open(schema_path, "r")))

    # Open the zip file that we will write results to
    timeString = time.strftime("%d%m%Y", time.localtime())

    # Set the xml root
    root = eTree.Element("DigitalContentData")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:noNamespaceSchemaLocation", schema_path)

    def get_tag(entry, tag, position=None):

        try:
            results = entry.get_tag(tag)
        # The tag is missing
        except KeyError:
            results = []

        # Return a specific position
        if position is not None:
            if position < len(results):
                return results[position]
            else:
                return "?"

        if not results:
            return "?"

        return results

    def conditional_add(parent, name, value):
        if value not in pynmrstar.utils.definitions.NULL_VALUES:
            tmp = eTree.SubElement(parent, name)
            tmp.text = value

    # Go through each entry
    for entry, release_date in entry_data:

        try:
            logging.info("Loading entry: %s" % entry)
            try:
                parsed = pynmrstar.Entry.from_database(entry)

                # Generate the xml
                DataRecord = eTree.SubElement(root, "DataRecord")
                DataRecord.set("ProviderID", str(entry))

                # Header
                Header = eTree.SubElement(DataRecord, "Header")
                DateProvided = eTree.SubElement(Header, "DateProvided")
                DateProvided.text = str(get_tag(parsed, "_Release.Date", 0))

                # If no date, set oldest possible date to conform to schema
                if DateProvided.text in ("None", ".", "?"):
                    DateProvided.text = "1969-12-31"

                RepositoryName = eTree.SubElement(Header, "RepositoryName")
                RepositoryName.text = "Biological Magnetic Resonance Data Bank (BMRB)"
                Owner = eTree.SubElement(Header, "Owner")
                Owner.text = "The Board of Regents of the University of Wisconsin System"

                # BibliographicData
                BibliographicData = eTree.SubElement(DataRecord, "BibliographicData")
                AuthorList = eTree.SubElement(BibliographicData, "AuthorList")

                # Go through the authors
                for ordinal, author in enumerate(zip(get_tag(parsed, "_Entry_author.Given_name"),
                                                     get_tag(parsed, "_Entry_author.Family_name"))):
                    Author = eTree.SubElement(AuthorList, "Author")
                    Author.set("ResearcherID", str(ordinal))
                    AuthorName = eTree.SubElement(Author, "AuthorName")
                    AuthorName.text = "%s %s" % (author[0], author[1])
                    Surname = eTree.SubElement(Author, "Surname")
                    Surname.text = author[1]
                    Forename = eTree.SubElement(Author, "Forename")
                    Forename.text = author[0]

                # Set the last author as the PI
                Author.set("AuthorRole", "Principle investigator")

                # Other tags in BibliographicData
                conditional_add(BibliographicData, "ItemTitle",
                                str(get_tag(parsed, "_Entry.Title", 0)).replace("\n", ""))
                Source = eTree.SubElement(BibliographicData, "Source")
                SourceURL = eTree.SubElement(Source, "SourceURL")
                SourceURL.text = f"https://bmrb.io/data_library/summary/index.php?bmrbId={entry}"
                PublisherDistributor = eTree.SubElement(Source, "PublisherDistributor")
                PublisherDistributor.text = "Biological Magnetic Resonance Data Bank"
                CreatedDate = eTree.SubElement(Source, "CreatedDate")
                CreatedDate.text = release_date.strftime("%Y")
                DepositedDate = eTree.SubElement(Source, "DepositedDate")
                DepositedDate.text = release_date.strftime("%Y-%m-%d")

                # Abstract
                Abstract = eTree.SubElement(DataRecord, "Abstract")
                Abstract.text = "Not captured"

                DescriptorsData = eTree.SubElement(DataRecord, "DescriptorsData")

                # Keywords
                keywords = get_tag(parsed, "_Struct_keywords.Keywords")
                if len(keywords) > 0:
                    KeywordsList = eTree.SubElement(DescriptorsData, "KeywordsList")
                    for keyword in keywords:
                        Keyword = eTree.SubElement(KeywordsList, "Keyword")
                        Keyword.text = keyword

                # Organisms
                organisms = get_tag(parsed, "_Entity_natural_src.Organism_name_scientific")
                for organism in organisms:
                    if organism != "?" and organism != "." and organism != "":
                        OrganismList = eTree.SubElement(DescriptorsData, "OrganismList")
                        conditional_add(OrganismList, "OrganismName", organism)

                # Genes - currently no entries have gene names but keep this in just in case
                genes = get_tag(parsed, "_Entity_natural_src.Host_org_gene")
                for gene in genes:
                    if gene != "?" and gene != "." and gene != "":
                        GeneNameList = eTree.SubElement(DescriptorsData, "GeneNameList")
                        conditional_add(GeneNameList, "GenName", gene)

                # Citations
                citations = parsed.get_saveframes_by_category("citations")
                if len(citations) > 0:
                    CitationList = eTree.SubElement(DataRecord, "CitationList")
                    for ordinal, citation in enumerate(citations):
                        Citation = eTree.SubElement(CitationList, "Citation")
                        Citation.set("CitationSeq", str(ordinal))
                        Citation.set("CitationType", "Cited Ref")
                        conditional_add(Citation, "CitationPubMedID", get_tag(citation, 'PubMed_ID', 0))
                        conditional_add(Citation, "CitationDOI", get_tag(citation, 'DOI', 0))
                        CitationText = eTree.SubElement(Citation, "CitationText")
                        conditional_add(CitationText, "FullCitation", "Not captured")
                        ParsedCitationData = eTree.SubElement(CitationText, "ParsedCitationData")
                        conditional_add(ParsedCitationData, "CitationArticleTitle",
                                        get_tag(citation, 'Title', 0).replace("\n", ""))
                        conditional_add(ParsedCitationData, "CitationJournal", get_tag(citation, 'Journal_abbrev', 0))
                        conditional_add(ParsedCitationData, "CitationSourceVolume",
                                        get_tag(citation, 'Journal_volume', 0))
                        conditional_add(ParsedCitationData, "CitationSourceIssue",
                                        get_tag(citation, 'Journal_issue', 0))
                        conditional_add(ParsedCitationData, "CitationFirstPage", get_tag(citation, 'Page_first', 0))
                        conditional_add(ParsedCitationData, "CitationPagination", get_tag(citation, 'Page_last', 0))
                        conditional_add(ParsedCitationData, "CitationYear", get_tag(citation, 'Year', 0))
                        conditional_add(ParsedCitationData, "CitationISSN", get_tag(citation, 'Journal_ISSN', 0))

                # We've added everything. Now validate this entry against the schema
                xmlschema.assertValid(etree.parse(BytesIO(xml_tostring(DataRecord, encoding="us-ascii"))))

            except IOError:
                logging.info("Skipping %d because no file found on disk." % entry)
        except Exception as err:
            import traceback
            print("An exception occurred while processing entry %d: %s" % (entry, str(err)))
            traceback.print_exc()
            sys.exit(1)

    # Do one final validation of the full tree
    xmlschema.assertValid(etree.parse(BytesIO(xml_tostring(root, encoding="us-ascii"))))

    # Remove the old files
    files_to_remove = os.listdir(result_location)
    for each_file in files_to_remove:
        if each_file.startswith("bmrb") and each_file.endswith(".xml.zip"):
            os.unlink(os.path.join(result_location, each_file))
            logging.info("Unlinking old file: %s" % each_file)

    # Write the results to a zip file
    result_zip = zipfile.ZipFile(os.path.join(result_location, "bmrb%s.xml.zip" % timeString), mode="w",
                                 compression=zipfile.ZIP_DEFLATED)
    result_zip.comment = ("BMRB entry citation information. Date: %s" % timeString).encode()
    result_zip.writestr("bmrb%s.xml" % timeString, xml_tostring(root, encoding="us-ascii"))
    result_zip.close()
