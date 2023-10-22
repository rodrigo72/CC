DROP TABLE IF EXISTS `mydb`.`FS_Node` ;

CREATE TABLE IF NOT EXISTS `mydb`.`FS_Node` (
  `IPv4_Address` VARCHAR(15) NOT NULL,
  `Number` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`IPv4_Address`),
  UNIQUE INDEX `IP_Address_UNIQUE` (`IPv4_Address` ASC) VISIBLE,
  UNIQUE INDEX `Number_UNIQUE` (`Number` ASC) VISIBLE)
ENGINE = InnoDB;


DROP TABLE IF EXISTS `mydb`.`File` ;

CREATE TABLE IF NOT EXISTS `mydb`.`File` (
  `Name` VARCHAR(100) NOT NULL,
  `Size` BIGINT NOT NULL,
  PRIMARY KEY (`Name`))
ENGINE = InnoDB;


DROP TABLE IF EXISTS `mydb`.`File_Chunk` ;

CREATE TABLE IF NOT EXISTS `mydb`.`File_Chunk` (
  `Number` INT NOT NULL,
  `Block_Size` INT NOT NULL,
  `Block_Offset` BIGINT NOT NULL,
  `File_Name` VARCHAR(100) NOT NULL,
  INDEX `fk_Bloco_File1_idx` (`File_Name` ASC) VISIBLE,
  PRIMARY KEY (`Block_Size`, `Block_Offset`),
  CONSTRAINT `fk_Bloco_File1`
    FOREIGN KEY (`File_Name`)
    REFERENCES `mydb`.`File` (`Name`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `mydb`.`FS_Node_has_File_Chunk`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`FS_Node_has_File_Chunk` ;

CREATE TABLE IF NOT EXISTS `mydb`.`FS_Node_has_File_Chunk` (
  `FS_Node_IPv4_Address` VARCHAR(15) NOT NULL,
  `File_Chunk_Block_Size` INT NOT NULL,
  `File_Chunk_Block_Offset` BIGINT NOT NULL,
  PRIMARY KEY (`FS_Node_IPv4_Address`, `File_Chunk_Block_Size`, `File_Chunk_Block_Offset`),
  INDEX `fk_FS_Node_has_File_Chunk_File_Chunk1_idx` (`File_Chunk_Block_Size` ASC, `File_Chunk_Block_Offset` ASC) VISIBLE,
  INDEX `fk_FS_Node_has_File_Chunk_FS_Node1_idx` (`FS_Node_IPv4_Address` ASC) VISIBLE,
  CONSTRAINT `fk_FS_Node_has_File_Chunk_FS_Node1`
    FOREIGN KEY (`FS_Node_IPv4_Address`)
    REFERENCES `mydb`.`FS_Node` (`IPv4_Address`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_FS_Node_has_File_Chunk_File_Chunk1`
    FOREIGN KEY (`File_Chunk_Block_Size` , `File_Chunk_Block_Offset`)
    REFERENCES `mydb`.`File_Chunk` (`Block_Size` , `Block_Offset`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;