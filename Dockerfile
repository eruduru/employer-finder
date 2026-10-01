FROM python:3.11-slim
WORKDIR /app
COPY employer_finder_app.py .
EXPOSE 7860
ENV PORT=7860
CMD ["python", "employer_finder_app.py"]
