FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies for document processing (unstructured, magic, etc.)
# Amazon Linux 2023 uses dnf
RUN dnf update -y && \
    dnf install -y \
    libmagic \
    poppler-utils \
    mesa-libGL \
    glib2 \
    && dnf clean all

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install Python dependencies
# --no-cache-dir to keep image size smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app ${LAMBDA_TASK_ROOT}/app

# Command to run the handler
CMD [ "app.main.handler" ]
