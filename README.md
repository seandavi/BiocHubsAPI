## BiocHubs API

This project provides a RESTful API for accessing and querying Bioconductor Hub (AnnotationHub, ExperimentHub) resources.

The Bioconductor Hubs are a collection of curated, versioned, and easily accessible genomic data resources for the R/Bioconductor ecosystem. 
The current system hosts over 100,000 resources including genomic annotations, experimental datasets, and reference genomes in various formats (e.g., FASTA, GTF, BAM, VCF).
The data are currently stored in SQLite databases with a minimal relational schema.
The goal is to convert these to a more robust and scalable backend (Postgres) and provide a modern API for accessing the data.

Over time, we plan to add more features such as authentication, user accounts, data submission, validation, curation, versioning, and more.

## Try me

You can try out the API (which may be down at times) at <https://ahub-api.cancerdatasci.org/docs> or to list resources at <https://ahub-api.cancerdatasci.org/api/v2/resources>