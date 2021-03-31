
-- ------------------ --
-- Server Table Views --
-- ------------------ --

-- Specimen View --
DROP VIEW IF EXISTS `mmeds_data1`.`SpecimenView`;
CREATE VIEW `mmeds_data1`.`SpecimenView` AS SELECT
`idSpecimen`,
`SpecimenID`,
`Specimen`.`user_id`,
`SpecimenCollectionDate`,
`SpecimenNotes`,
`SpecimenCollectionTime`,
`SpecimenWeight`,
`StudyName`
FROM ( `Specimen` INNER JOIN
    ( `Experiment` INNER JOIN
        `Study` ON `Study_idStudy` = `idStudy` )
    ON `Experiment_idExperiment` = `idExperiment` );

-- Sample View --
DROP VIEW IF EXISTS `mmeds_data1`.`SampleView`;
CREATE VIEW `mmeds_data1`.`SampleView` AS SELECT
`idSample`,
`Aliquot_idAliquot`,
`SampleID`,
`SampleDatePerformed`,
`SampleProcessor`,
`SampleProtocolNotes`,
`SampleProtocolID`,
`SampleConditions`,
`SampleTool`,
`SampleToolVersion`
FROM ( `Sample` INNER JOIN
    ( `SampleProtocol` INNER JOIN
        `SampleProtocols` ON `SampleProtocols_idSampleProtocols` = `idSampleProtocols` )
    ON `SampleProtocol_idSampleProtocol` = `idSampleProtocol` );

-- SubjectType View --
DROP VIEW IF EXISTS `mmeds_data1`.`SubjectTypeView`;
CREATE VIEW `mmeds_data1`.`SubjectTypeView` AS SELECT
`StudyName`,
`Subjects_idSubjects`,
`AnimalSubjects_idAnimalSubjects` FROM
( `SubjectType` INNER JOIN
    (`SubjectType_has_Experiment` INNER JOIN
        ( `Experiment` INNER JOIN
            `Study` ON `Study_idStudy` = `idStudy` )
        ON `Experiment_idExperiment` = `idExperiment`)
    ON `idSubjectType` = `SubjectType_idSubjectType`);


-- Human Subject View --
DROP VIEW IF EXISTS `mmeds_data1`.`SubjectView`;
CREATE VIEW `mmeds_data1`.`SubjectView` AS SELECT
`idSubjects`,
`HostSubjectId`,
`Nationality`,
`Sex`,
`BirthYear`,
`StudyName` FROM
( `Subjects` INNER JOIN `SubjectTypeView` ON `idSubjects` = `Subjects_idSubjects`);
