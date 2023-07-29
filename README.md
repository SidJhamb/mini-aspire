# Mini-Aspire API

This is the source code for the Mini-Aspire API.

## Prerequisites
Following are the **prerequisites** that need to be installed beforehand, before being able to run the service.
* Docker
* [Docker Compose](https://docs.docker.com/compose/)

## Setup
Execute the following commands from the root directory of the project to run the API.
```
cd mini-aspire
docker-compose build
docker-compose up
```

This starts a server on `localhost 127.0.0.1` listening to port `8000`.

## Technology Stack
* Web framework : Django, Django REST framework
* Database : PostgreSQL
* Programming Language : Python
* Containerization : Docker, docker-compose

## Source Code Structure
```
app                       
  ├── app                  // Root Django project
  │   ├── ...
  │   ├── settings.py      // Django settings file
  │   └── urls.py          // Root URL mappings for the app
  ├── core                 // Django App encapsulating custom management commands and database models.
  │   ├── management        
  │   │   ├── commands/    // Custom management commands
  │   ├── migrations/      // Django migrations
  │   ├── tests/           // Unit tests for the custom management commands.
  │   ├── backend.py       // Contains the custom authentication logic applicable for the loan app.
  │   └── models.py        // Database models
  ├── loan                 // Django App serving the mini-aspire API.
  │   ├── serializers.py   // Django serializers.
  │   ├── urls.py          // URL mappings for the loan app.
  │   ├── views.py         // View handlers to serve API requests.
  │   ├── tests.py         // Unit tests for the mini-aspire API.
  └── manage.py
.gitignore
.dockerignore              
docker-compose.yml         // Docker compose configuration file.
Dockerfile                 // The Dockerfile
requirements.txt           // The file enlisting python module requirements.

```

## Swagger Documentation
The Swagger documentation, as per the OpenAPI Specification, can be accessed at `http://127.0.0.1:8000/docs/`, after
`docker-compose up` has run successfully.

## Unit Tests
Execute the following command from the root directory of the project to run unit tests.
```
cd mini-aspire
docker-compose run --rm app sh -c "python manage.py test"
```

## REST API

The following REST API endpoints are exposed on the localhost after `docker-compose up` has run
successfully and started serving the mini-aspire API.

### **POST /user**
The API supports a simplified version of user authentication. This particular endpoint allows the user to supply
a `user_name` and `is_admin` in the request body, which post successful creation of the `User` record, defined in
[models.py](/app/core/models.py), serves as a unique identifier for any user issuing loan/repayment related API calls.
The `user_name` value, indicated in the response JSON below, needs to be present in the request header for the API 
calls, for which authentication is applicable. 

The `is_admin` boolean flag in the request body, allows the set whether the requested user should have admin privileges or not.

##### Sample Request
```
curl --location --request POST 'http://127.0.0.1:8000/user' \
--header 'Content-Type: application/json' \
--data '{
    "user_name": "sample_user",
    "is_admin": true
}'
```

##### Sample Response
```
"POST /user HTTP/1.1" 201 22

{"user_name":"sample_user"}
```

### **POST /loan**
This endpoint allows authenticated users to create loan requests and store the corresponding record in the database.
For the loan, the request body accepts the two fundamental attributes, namely `amount` and `terms`. As a downstream 
step to this, `repayment` records are also created in the database. For example, if the `terms` requested are 5, then 
5 `repayment` records will be created.

This API calls returns the ID of the newly created loan record in the response, so that the loan ID could be used
for making repayments, explained in the following section.

##### Sample Request
```
curl --location --request POST 'http://127.0.0.1:8000/loan' \
--header 'username: sample_user' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 3000,
    "terms": 5
}'
```

##### Sample Response
```
"POST /loan HTTP/1.1" 200 8

{
    "id": 1
}
```

### **GET /loan**
This endpoint allows authenticated users to view all the loans mapped against them in the database, along with the
scheduled repayments for each loan.

##### Sample Request
```
curl --location --request GET 'http://127.0.0.1:8000/loan' \
--header 'username: sample_user'
```

##### Sample Response
```
"GET /loan HTTP/1.1" 200 647

[
    {
        "id": 1,
        "amount": 1000,
        "terms": 3,
        "repayments": [
            {
                "id": 1,
                "amount": 333,
                "status": "PAID",
                "due_date": "2023-08-04"
            },
            ...
        ],
        "status": "PAID"
    },
    {
        "id": 3,
        "amount": 3000,
        "terms": 5,
        "repayments": [
            {
                "id": 9,
                "amount": 600,
                "status": "PENDING",
                "due_date": "2023-08-05"
            },
            {
                "id": 10,
                "amount": 600,
                "status": "PENDING",
                "due_date": "2023-08-12"
            },
            ...
        ],
        "status": "PENDING"
    }
]
```

### **PUT /approval/<loan_id>**
This endpoint can be used by the admin user to mark a loan as approved. If this call is attemped by a non-admin user,
the API will return a 401 error.

##### Sample Request
```
curl --location --request PUT 'http://127.0.0.1:8000/approval/2' \
--header 'username: admin_user'
```

##### Sample Response
```
"PUT /approval/2 HTTP/1.1" 200 42

{
    "message": "Loan, with ID 2 is approved."
}
```

### **PUT /repayment/<loan_id>/<repayment_id>**
* This allows the authenticated non-admin users to make repayment for a loan, given the loan ID and repayment ID in the
  API URL.
* Repayments can only be made for a loan that has been approved by the admin. If a repayment is attempted for a loan
  that is still in the PENDING state, the API will return a 400 error.
* If the amount in the request body is less than the expected repayment amount, the API will return a 400 error.
* The date on which a loan is created and the repayment due dates are populated accordingly in the corresponding 
  database tables, but for simplicity sake, the dates are not taken into account for deciding whether a repayment has
  to be accepted or not. 
* In case the repayment amount is more than the expected amount, the pending repayment amounts will be rebalanced as a  
  downstream step to this API call handling.<br><br>

  For example, if there are 3 repayments for a loan,<br><br>

  Repayment 1, Amount = 100, Status = Pending  
  Repayment 2, Amount = 100, Status = Pending  
  Repayment 3, Amount = 100, Status = Pending<br><br>

  And if the API call is made to repay 1, with amount 120, then post the API call handling, following will be the status
  of all the repayments.<br><br>

  Repayment 1, Amount = 120, Status = Paid  
  Repayment 2, Amount = 90, Status = Pending  
  Repayment 3, Amount = 90, Status = Pending<br><br>

  i.e. The total loan amount initially owed was 300. Post completion of the first repayment, the balanced amount to be repaid
  became 180 (300-120). This balance amount is divided equally among all the pending repayments. So, 90 (180/2) becomes
  the amount for the remaining pending repayments and is saved accordingly in the database.

* If all the repayments for a loan have been paid, then the loan will also be marked as paid. 

##### Sample Request
```
curl --location --request PUT 'http://127.0.0.1:8000/repayment/3/9' \
--header 'username: sample_user' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 600
}'
```

##### Sample Response
```
"PUT /repayment/3/9 HTTP/1.1" 200 47

{
    "message": "Repayment successfully completed."
}
```
