FROM eclipse-temurin:21-jdk-alpine

WORKDIR /app

# Copy Maven wrapper and pom.xml first to cache dependencies
COPY .mvn/ .mvn
COPY mvnw pom.xml ./

# Convert CRLF to LF in mvnw just in case, and make it executable
RUN sed -i 's/\r$//' mvnw && chmod +x mvnw

# Resolve dependencies (go offline)
RUN ./mvnw dependency:go-offline -B

# Copy the source code
COPY src ./src

# Default command to run the application using spring-boot:run for development
# This allows hot-reloading if devtools is present, or just runs it simply.
# For production, we would build a jar and use ENTRYPOINT ["java", "-jar", "app.jar"]
CMD ["./mvnw", "spring-boot:run"]
