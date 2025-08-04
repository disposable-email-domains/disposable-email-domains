### Spring Boot
contributed by [@thesauravpoddar](https://github.com/thesauravpoddar)
```java
import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;
import org.springframework.beans.factory.annotation.Value;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Target({ElementType.FIELD, ElementType.PARAMETER})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = EmailDomainValidator.class)
@interface NonDisposableEmail {
    String message() default "Disposable email addresses are not allowed";
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}

public class EmailDomainValidator implements ConstraintValidator<NonDisposableEmail, String> {

    private final Set<String> blocked;

    public EmailDomainValidator(@Value("${app.security.jwt.disposable-emails}") String domains) {
        this.blocked = Stream.of(domains.split(","))
                             .map(String::toLowerCase)
                             .collect(Collectors.toSet());
    }

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null || !email.contains("@")) {
            return true;
        }
        int atIndex = email.lastIndexOf("@") + 1;
        int dotIndex = email.lastIndexOf(".");
        String domain = email.substring(atIndex, dotIndex).toLowerCase();

        return !blocked.contains(domain);
    }
}

```
> Note: Add this to your `application.yml`:
> 
> ```yaml
> app:
>   security:
>     jwt:
>       disposable-emails: 10minutemail,20minutemail,33mail,mailinator,trashmail,temp-mail,yopmail
> ```
>
> Maven dependency (pom.xml):
> ```xml
> <dependency>
>   <groupId>org.springframework.boot</groupId>
>   <artifactId>spring-boot-starter-validation</artifactId>
> </dependency>
> ```
> Note: Adding disposable emails to your spring boot backend is not good
> So here the 2 ways in which you can dynamically add disposable emails
> Method 1) Adding an external file like DISPOSABLE_EMAILS.txt abd laod them dynamically at runtime
> Here is the exaple code for that
```java
import jakarta.annotation.PostConstruct;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashSet;
import java.util.Set;

public class EmailDomainValidator implements ConstraintValidator<NonDisposableEmail, String> {

    private final ResourceLoader resourceLoader;
    private Set<String> blockedDomains = new HashSet<>();

    public EmailDomainValidator(ResourceLoader resourceLoader) {
        this.resourceLoader = resourceLoader;
    }

    @PostConstruct
    public void init() {
        try {
            Resource resource = resourceLoader.getResource("classpath:disposable_emails.txt");
            BufferedReader reader = new BufferedReader(new InputStreamReader(resource.getInputStream()));
            String line;
            while ((line = reader.readLine()) != null) {
                blockedDomains.add(line.trim().toLowerCase());
            }
        } catch (Exception e) {
            throw new RuntimeException("The list that you are trying to access does not exist", e);
        }
    }

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null || !email.contains("@")) return true;
        String domain = email.substring(email.lastIndexOf("@") + 1).toLowerCase();
        return !blockedDomains.contains(domain);
    }
}

```
Mathod 2) : By using an external Api and integrating it into your spring boot 
Here is an exapmple code for that
#Use RestTemplate to call an Api
```java
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.ResponseEntity;

public class EmailDomainValidator implements ConstraintValidator<NonDisposableEmail, String> {

    private final RestTemplate restTemplate = new RestTemplate();

    @Override
    public boolean isValid(String email, ConstraintValidatorContext context) {
        if (email == null || !email.contains("@")) return true;

        try {
            String apiUrl = "https://open.kickbox.com/v1/disposable/" + email; // Mock-style
            ResponseEntity<String> response = restTemplate.getForEntity(apiUrl, String.class);

            // Let's assume API returns `true` if it's disposable
            return !"true".equalsIgnoreCase(response.getBody());
        } catch (Exception e) {
            // On API failure, allow the email (fail-safe)
            return true;
        }
    }
}
```





