FROM eclipse-temurin:17-jre-alpine

LABEL maintainer="yasmine-jhinaoui"

WORKDIR /app

# Utilisateur non-root (bonne pratique de sécurité)
RUN addgroup -S app && adduser -S app -G app

COPY target/timesheet-devops-*.jar app.jar

USER app

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
