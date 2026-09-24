FROM eclipse-temurin:17-jre-alpine

LABEL maintainer="yasmine-jhinaoui"

WORKDIR /app

# Utilisateur non-root (bonne pratique de sécurité)
RUN addgroup -S app && adduser -S app -G app

COPY target/timesheet-devops-1.0.jar app.jar

USER app

EXPOSE 8082

ENTRYPOINT ["java", "-jar", "app.jar"]
