
-- ------------------ --
-- Server Table Views --
-- ------------------ --

-- Specimen View --
DROP VIEW IF EXISTS `mmeds_data1`.`SpecimenView`;
CREATE VIEW IF NOT EXISTS `mmeds_data1`.`SpecimenView` AS
SELECT
`idSpecimen`,
`SpecimenID`,
`SpecimenCollectionDate`,
`SpecimenInformation`,
`SpecimenCollectionTime`,
`SpecimenWeight`,
`StudyName`
FROM
( `Specimen` INNER JOIN
 ( `Experiment` INNER JOIN
 `Study` ON `Study_idStudy` = `idStudy` )
 ON `Experiment_idExperiment` = `idExperiment` );
