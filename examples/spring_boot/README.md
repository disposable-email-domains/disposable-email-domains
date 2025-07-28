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
