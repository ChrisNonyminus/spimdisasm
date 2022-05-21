#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Decompollaborate
# SPDX-License-Identifier: MIT

from __future__ import annotations

from ... import common

from ..MipsElementBase import ElementBase


class SymbolBase(ElementBase):
    def __init__(self, context: common.Context, inFileOffset: int, vram: int|None, name: str, words: list[int], sectionType: common.FileSectionType):
        super().__init__(context, inFileOffset, vram, name, words, sectionType)

        self.endOfLineComment: list[str] = []

        self.contextSym: common.ContextSymbol|None = None
        if self.vram is not None:
            contextSym = self.context.getAnySymbol(self.vram)
            if contextSym is None:
                symName: str|None = self.name
                if symName == "":
                    symName = None
                contextSym = self.context.addSymbol(self.vram, symName, self.sectionType)
                contextSym.isAutogenerated = True
                contextSym.isDefined = True
            self.contextSym = contextSym
            self.name = contextSym.name


    def generateAsmLineComment(self, localOffset: int, wordValue: int|None = None) -> str:
        if not common.GlobalConfig.ASM_COMMENT:
            return ""

        offsetHex = f"{localOffset + self.inFileOffset + self.commentOffset:06X}"

        vramHex = ""
        if self.vram is not None:
            currentVram = self.getVramOffset(localOffset)
            vramHex = f"{currentVram:08X} "

        wordValueHex = ""
        if wordValue is not None:
            wordValueHex = f"{wordValue:08X} "

        return f"/* {offsetHex} {vramHex}{wordValueHex}*/"

    def getSymbolAtVramOrOffset(self, localOffset: int) -> common.ContextSymbolBase | None:
        if self.vram is not None:
            currentVram = self.getVramOffset(localOffset)
            return self.context.getAnySymbol(currentVram)
        return self.context.getOffsetSymbol(self.inFileOffset + localOffset, self.sectionType)

    def getLabel(self) -> str:
        if self.contextSym is not None:
            return self.getLabelFromSymbol(self.contextSym)

        offsetSym = self.context.getOffsetSymbol(self.inFileOffset, self.sectionType)
        return self.getLabelFromSymbol(offsetSym)


    def renameBasedOnSection(self):
        if not common.GlobalConfig.AUTOGENERATED_NAMES_BASED_ON_SECTION_TYPE:
            return

        if self.sectionType != common.FileSectionType.Rodata and self.sectionType != common.FileSectionType.Bss:
            return

        if self.vram is None:
            return

        if self.contextSym is not None:
            if not self.contextSym.isAutogenerated:
                return

            if self.sectionType == common.FileSectionType.Rodata:
                if self.contextSym.type != "@jumptable":
                    self.contextSym.name = f"R_{self.vram:08X}"
            elif self.sectionType == common.FileSectionType.Bss:
                self.contextSym.name = f"B_{self.vram:08X}"
            self.name = self.contextSym.name

    def renameBasedOnType(self):
        pass


    def analyze(self):
        self.renameBasedOnSection()
        self.renameBasedOnType()


    def disassembleAsData(self) -> str:
        output = self.getLabel()

        canReferenceSymbolsWithAddends = self.vram in self.context.dataSymbolsWithReferencesWithAddends
        canReferenceConstants = self.vram in self.context.dataReferencingConstants

        localOffset = 0
        i = 0

        for w in self.words:
            label = ""
            if localOffset != 0:
                # Possible symbols in the middle
                contextSym = self.getSymbolAtVramOrOffset(localOffset)
                if contextSym is not None:
                    label = "\n" + contextSym.getSymbolLabel() + "\n"

            value = f"0x{w:08X}"

            # .elf relocated symbol
            possibleReference = self.context.getRelocSymbol(self.inFileOffset + localOffset, self.sectionType)
            if possibleReference is not None:
                value = possibleReference.getNamePlusOffset(w)

            # This word could be a reference to a symbol
            symbol = self.context.getGenericSymbol(w, tryPlusOffset=canReferenceSymbolsWithAddends)
            if symbol is not None:
                value = symbol.getSymbolPlusOffset(w)
            elif canReferenceConstants:
                constant = self.context.getConstant(w)
                if constant is not None:
                    value = constant.name

            comment = self.generateAsmLineComment(localOffset)
            output += f"{label}{comment} .word {value}"
            if i < len(self.endOfLineComment):
                output += self.endOfLineComment[i]
            output += "\n"
            localOffset += 4
            i += 1

        return output


    def disassemble(self) -> str:
        return self.disassembleAsData()
