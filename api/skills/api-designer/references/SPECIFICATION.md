# Starter OpenAPI document

## Contents

- How to use
- Document

## How to use

1. Rename the resource (`bookings`) and its schemas to your domain.
2. Keep the shared `Problem` schema, the shared responses, the `Limit`, `Cursor` and
   `IdempotencyKey` parameters, and the security scheme.
3. Replace the `example.invalid` provider URLs with the values the user gave you.
4. List every scope used by an operation under `scopes`.
5. Lint with `assets/spectral.yaml`.

## Document

```yaml
openapi: 3.1.0
info:
  title: Room Bookings API
  version: 1.0.0
  description: Create, list and confirm room bookings.
  contact:
    name: Bookings team
    email: bookings@example.invalid
servers:
  - url: https://api.example.invalid/v1
security:
  - oidc: []
tags:
  - name: bookings
    description: Room bookings and their lifecycle.
paths:
  /bookings:
    get:
      operationId: listBookings
      summary: List bookings
      description: Returns the caller's bookings, newest first, one cursor page at a time.
      tags: [bookings]
      security:
        - oidc: [bookings:read]
      parameters:
        - name: status
          in: query
          description: Return only bookings in this state.
          schema:
            $ref: '#/components/schemas/BookingStatus'
        - $ref: '#/components/parameters/Limit'
        - $ref: '#/components/parameters/Cursor'
      responses:
        '200':
          description: A page of bookings.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BookingPage'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '429':
          $ref: '#/components/responses/TooManyRequests'
    post:
      operationId: createBooking
      summary: Create a booking
      description: Creates a booking in the `pending` state for the caller.
      tags: [bookings]
      security:
        - oidc: [bookings:write]
      parameters:
        - $ref: '#/components/parameters/IdempotencyKey'
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BookingCreate'
      responses:
        '201':
          description: Booking created.
          headers:
            Location:
              description: URL of the new booking.
              schema:
                type: string
                format: uri-reference
                maxLength: 256
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Booking'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '422':
          $ref: '#/components/responses/Invalid'
        '429':
          $ref: '#/components/responses/TooManyRequests'
  /bookings/{id}:
    parameters:
      - $ref: '#/components/parameters/BookingId'
    get:
      operationId: getBooking
      summary: Get a booking
      description: Returns one booking. A booking owned by someone else yields 404.
      tags: [bookings]
      security:
        - oidc: [bookings:read]
      responses:
        '200':
          description: The booking.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Booking'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'
  /bookings/{id}/confirm:
    parameters:
      - $ref: '#/components/parameters/BookingId'
    post:
      operationId: confirmBooking
      summary: Confirm a booking
      description: Moves a booking from `pending` to `confirmed`. Any other current state yields 409.
      tags: [bookings]
      security:
        - oidc: [bookings:write]
      responses:
        '200':
          description: The confirmed booking.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Booking'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'
        '409':
          $ref: '#/components/responses/Conflict'
components:
  securitySchemes:
    oidc:
      type: oauth2
      description: OpenID Connect provider; replace the placeholder URLs.
      flows:
        authorizationCode:
          authorizationUrl: https://auth.example.invalid/oauth2/authorize
          tokenUrl: https://auth.example.invalid/oauth2/token
          scopes: &scopes
            bookings:read: Read bookings
            bookings:write: Create and change bookings
        clientCredentials:
          tokenUrl: https://auth.example.invalid/oauth2/token
          scopes: *scopes
  parameters:
    BookingId:
      name: id
      in: path
      required: true
      description: Booking identifier.
      schema:
        type: string
        format: uuid
    Limit:
      name: limit
      in: query
      description: Page size.
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 25
    Cursor:
      name: cursor
      in: query
      description: Opaque cursor from a previous page's `nextCursor`.
      schema:
        type: string
        maxLength: 256
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      description: Client-chosen key; a retry with the same key replays the first result.
      schema:
        type: string
        maxLength: 64
  schemas:
    BookingStatus:
      type: string
      enum: [pending, confirmed, cancelled]
      description: Lifecycle state. pending -> confirmed -> cancelled; pending -> cancelled.
    BookingCreate:
      type: object
      additionalProperties: false
      required: [roomId, startsAt, endsAt]
      properties:
        roomId:
          type: string
          format: uuid
        startsAt:
          type: string
          format: date-time
        endsAt:
          type: string
          format: date-time
        note:
          type: string
          maxLength: 500
    Booking:
      type: object
      required: [id, roomId, status, startsAt, endsAt, createdAt]
      properties:
        id:
          type: string
          format: uuid
          readOnly: true
        roomId:
          type: string
          format: uuid
        status:
          $ref: '#/components/schemas/BookingStatus'
        startsAt:
          type: string
          format: date-time
        endsAt:
          type: string
          format: date-time
        note:
          type: string
          maxLength: 500
        createdAt:
          type: string
          format: date-time
          readOnly: true
    BookingPage:
      type: object
      required: [items, nextCursor]
      properties:
        items:
          type: array
          maxItems: 100
          items:
            $ref: '#/components/schemas/Booking'
        nextCursor:
          type: [string, 'null']
          maxLength: 256
    Problem:
      type: object
      required: [type, title, status]
      properties:
        type:
          type: string
          format: uri-reference
          maxLength: 256
        title:
          type: string
          maxLength: 200
        status:
          type: integer
          minimum: 100
          maximum: 599
        detail:
          type: string
          maxLength: 1000
        instance:
          type: string
          format: uri-reference
          maxLength: 256
        errors:
          type: array
          maxItems: 100
          items:
            type: object
            required: [field, message]
            properties:
              field:
                type: string
                maxLength: 200
              message:
                type: string
                maxLength: 500
  responses:
    Unauthorized:
      description: Missing or invalid credentials.
      content:
        application/problem+json:
          schema:
            $ref: '#/components/schemas/Problem'
    NotFound:
      description: The resource does not exist or is not visible to the caller.
      content:
        application/problem+json:
          schema:
            $ref: '#/components/schemas/Problem'
    Conflict:
      description: The current state does not allow this operation.
      content:
        application/problem+json:
          schema:
            $ref: '#/components/schemas/Problem'
    Invalid:
      description: The request body failed validation.
      content:
        application/problem+json:
          schema:
            $ref: '#/components/schemas/Problem'
    TooManyRequests:
      description: Rate limit exceeded.
      headers:
        Retry-After:
          description: Seconds to wait before retrying.
          schema:
            type: integer
            minimum: 0
      content:
        application/problem+json:
          schema:
            $ref: '#/components/schemas/Problem'
```
