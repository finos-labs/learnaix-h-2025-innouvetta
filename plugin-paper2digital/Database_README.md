
# Moodle App - Snowflake Database Setup

This document provides the complete setup guide for the Snowflake database tables required for the **Moodle PDF management application**.

## Prerequisites
- Snowflake account with appropriate privileges
- Access to `MOODLE_APP` database
- `COMPUTE_WH` warehouse (or equivalent)

## Database Schema Overview
The application uses three main tables:

1. **COURSES** - Stores course information  
2. **COURSE_PDFS** - Stores PDF file references with Google Drive links  
3. **PDF_OCR_CACHE** - Caches OCR-processed text content from PDFs  

## Table Creation Scripts

### 1. COURSES Table
```sql
CREATE OR REPLACE TABLE MOODLE_APP.PUBLIC.COURSES (
    COURSE_ID VARCHAR(50) NOT NULL,
    COURSE_NAME VARCHAR(100),
    PRIMARY KEY (COURSE_ID)
);
```

### 2. COURSE_PDFS Table
```sql
CREATE OR REPLACE TABLE MOODLE_APP.PUBLIC.COURSE_PDFS (
    COURSE_ID VARCHAR(50) NOT NULL,
    CHAPTER_NAME VARCHAR(100) NOT NULL,
    PDF_URI VARCHAR(500) NOT NULL,
    PRIMARY KEY (COURSE_ID, CHAPTER_NAME, PDF_URI),
    FOREIGN KEY (COURSE_ID) REFERENCES MOODLE_APP.PUBLIC.COURSES(COURSE_ID)
);
```

### 3. PDF_OCR_CACHE Table
```sql
CREATE OR REPLACE TABLE MOODLE_APP.PUBLIC.PDF_OCR_CACHE (
    COURSE_ID VARCHAR(50) NOT NULL,
    CHAPTER_NAME VARCHAR(100) NOT NULL,
    PDF_URI VARCHAR(500),
    OCR_TEXT VARCHAR(16777216),
    LAST_UPDATED TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (COURSE_ID, CHAPTER_NAME)
);
```

## Sample Data Insertion

### Insert Sample Courses
```sql
INSERT INTO MOODLE_APP.PUBLIC.COURSES (COURSE_ID, COURSE_NAME)
VALUES
    ('compiler', 'compiler'),
    ('compiler_construction', 'compiler_construction');
```

### Insert Sample Course PDFs
```sql
INSERT INTO MOODLE_APP.PUBLIC.COURSE_PDFS (COURSE_ID, CHAPTER_NAME, PDF_URI)
VALUES
    ('compiler', '1st', 'https://drive.google.com/file/d/1tz8lu_ZDv4LMpm8096DEOCectMTWqC8j/view?usp=sharing'),
    ('compiler', 'lec01-Lexical Analysis', 'https://drive.google.com/file/d/1tUzGAgEuUtuXvGPGGKEwM675vtDPf_nj/view?usp=sharing'),
    ('compiler_construction', '2nd', 'https://drive.google.com/file/d/1t0e_ZiBJZG839TcMOx-afnJ0kbpvoyXO/view?usp=sharing');
```

**Note:** The `PDF_OCR_CACHE` table will be populated automatically by the Python application during OCR processing.

## Complete Setup Script

```sql
-- Set context
USE DATABASE MOODLE_APP;
USE SCHEMA PUBLIC;
USE WAREHOUSE COMPUTE_WH;

-- Create tables
CREATE OR REPLACE TABLE COURSES (
    COURSE_ID VARCHAR(50) NOT NULL,
    COURSE_NAME VARCHAR(100),
    PRIMARY KEY (COURSE_ID)
);

CREATE OR REPLACE TABLE COURSE_PDFS (
    COURSE_ID VARCHAR(50) NOT NULL,
    CHAPTER_NAME VARCHAR(100) NOT NULL,
    PDF_URI VARCHAR(500) NOT NULL,
    PRIMARY KEY (COURSE_ID, CHAPTER_NAME, PDF_URI),
    FOREIGN KEY (COURSE_ID) REFERENCES COURSES(COURSE_ID)
);

CREATE OR REPLACE TABLE PDF_OCR_CACHE (
    COURSE_ID VARCHAR(50) NOT NULL,
    CHAPTER_NAME VARCHAR(100) NOT NULL,
    PDF_URI VARCHAR(500),
    OCR_TEXT VARCHAR(16777216),
    LAST_UPDATED TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (COURSE_ID, CHAPTER_NAME)
);

-- Insert sample data
INSERT INTO COURSES (COURSE_ID, COURSE_NAME)
VALUES
    ('compiler', 'compiler'),
    ('compiler_construction', 'compiler_construction');

INSERT INTO COURSE_PDFS (COURSE_ID, CHAPTER_NAME, PDF_URI)
VALUES
    ('compiler', '1st', 'https://drive.google.com/file/d/1tz8lu_ZDv4LMpm8096DEOCectMTWqC8j/view?usp=sharing'),
    ('compiler', 'lec01-Lexical Analysis', 'https://drive.google.com/file/d/1tUzGAgEuUtuXvGPGGKEwM675vtDPf_nj/view?usp=sharing'),
    ('compiler_construction', '2nd', 'https://drive.google.com/file/d/1t0e_ZiBJZG839TcMOx-afnJ0kbpvoyXO/view?usp=sharing');

-- Commit changes
COMMIT;
```

## Verification Queries

```sql
-- Check courses
SELECT * FROM MOODLE_APP.PUBLIC.COURSES;

-- Check course PDFs
SELECT * FROM MOODLE_APP.PUBLIC.COURSE_PDFS;

-- Check OCR cache
SELECT * FROM MOODLE_APP.PUBLIC.PDF_OCR_CACHE;

-- Count records by table
SELECT 'COURSES' AS TABLE_NAME, COUNT(*) AS RECORD_COUNT FROM COURSES
UNION ALL
SELECT 'COURSE_PDFS' AS TABLE_NAME, COUNT(*) AS RECORD_COUNT FROM COURSE_PDFS
UNION ALL
SELECT 'PDF_OCR_CACHE' AS TABLE_NAME, COUNT(*) AS RECORD_COUNT FROM PDF_OCR_CACHE;
```
