<?php

// Test file with intentional errors for LSP watcher verification

class TestClass
{
    public function testMethod()
    {
        // Undefined variable
        echo $undefinedVariable;

        // Calling undefined function
        $result = undefinedFunction();

        // Type error - passing string to int parameter
        $this->intMethod("not an int");

        // Missing semicolon
        $x = 5

        return $result;
    }

    public function intMethod(int $value): void
    {
        echo $value;
    }
}

// Calling method on non-object
$notAnObject = "string";
$notAnObject->someMethod();

// Undefined class
$obj = new UndefinedClass();
