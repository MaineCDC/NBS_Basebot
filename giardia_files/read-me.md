### Structure
```mermaid
classDiagram
    class GiardiaCaseReview{
        +CheckLabName()
        +CheckLabTestType()
        +CheckLabTestResult()
        +CheckSpecimenSource()
        +CheckDateSpecimenCollected()
        +CheckIllnessOnsetDate()
        +CheckAgeAtOnset()
        +CheckAgeAtOnsetUnit()
        +CheckWasSymptomatic()
        +CheckWasHospitalized()
        +CheckHospital()
        +CheckAdmissionDate()
        +CheckDischargeDate()
        +CheckDurationInHospital()
        +CheckDeath()
        +CheckPregnancyStatus()
        +CheckPatientTreated()
        +CheckImmuneCompromised()
        +CheckCoInfection()
        +CheckDiseaseAcquired()
        +CheckTransmissionMode()
        +CheckDetectionMode()
        +CheckConfirmationMethod()
        +CheckConfirmationDate()
        +CheckCaseStatus()
        +CheckDateClosed()
    }



### Extended
```mermaid
flowchart TD
   %% CheckCaseStatus
   A1 --> A1[Check lab name]
   A1 --> A2[Check l]

   
   End[End]
```